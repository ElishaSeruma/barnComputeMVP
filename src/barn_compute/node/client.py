"""CA-verified coordinator client for node enrolment."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import httpx

from ..api_models import decode_binary, encode_binary
from ..errors import BarnError, ErrorCode
from ..models import (
    EnrolmentChallenge,
    EnrolmentReceipt,
    EnrolmentResult,
    EnrolmentStatus,
)
from .service import NodeService


class CoordinatorClient:
    def __init__(
        self,
        base_url: str,
        ca_certificate: Path,
        *,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not base_url.startswith("https://") and transport is None:
            raise BarnError(ErrorCode.CONFIGURATION, "Coordinator URL must use HTTPS")
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            verify=str(ca_certificate),
            timeout=httpx.Timeout(timeout, connect=min(timeout, 5.0)),
            follow_redirects=False,
            transport=transport,
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> CoordinatorClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @staticmethod
    def _raise_for_error(response: httpx.Response) -> None:
        if response.is_success:
            return
        try:
            error = response.json()["error"]
            code = ErrorCode(error["code"])
            message = error["message"]
        except (KeyError, TypeError, ValueError):
            code = ErrorCode.INVALID_REQUEST
            message = f"Coordinator returned HTTP {response.status_code}"
        raise BarnError(code, message)

    def submit_enrolment(
        self,
        node: NodeService,
        invite_code: str,
    ) -> EnrolmentReceipt:
        metadata = node.load_metadata()
        challenge_response = self.client.post(
            "/v1/enrolments/challenge",
            json={"invite_code": invite_code, "node_id": str(metadata.node_id)},
        )
        self._raise_for_error(challenge_response)
        challenge = EnrolmentChallenge.model_validate(challenge_response.json())
        submission = node.create_submission(challenge)
        response = self.client.post(
            "/v1/enrolments",
            json={
                "invite_code": invite_code,
                "node_id": str(submission.node_id),
                "node_name": submission.node_name,
                "advertised_host": submission.advertised_host,
                "peer_port": submission.peer_port,
                "protocol_version": submission.protocol_version,
                "identity_public_key": encode_binary(submission.identity_public_key),
                "csr_pem": encode_binary(submission.csr_pem),
                "challenge": submission.challenge,
                "proof": encode_binary(submission.proof),
            },
        )
        self._raise_for_error(response)
        payload = response.json()
        receipt = EnrolmentReceipt(
            request_id=UUID(payload["request_id"]),
            receipt=payload["receipt"],
            status=payload["status"],
        )
        node.record_receipt(receipt.request_id, receipt.receipt)
        return receipt

    def poll_enrolment(self, node: NodeService) -> EnrolmentResult:
        metadata = node.load_metadata()
        if metadata.enrolment_request_id is None:
            raise BarnError(ErrorCode.CONFIGURATION, "Node has no pending enrolment")
        response = self.client.get(
            f"/v1/enrolments/{metadata.enrolment_request_id}",
            headers={"X-Barn-Enrolment-Receipt": node.load_receipt()},
        )
        self._raise_for_error(response)
        payload = response.json()
        result = EnrolmentResult(
            request_id=payload["request_id"],
            status=EnrolmentStatus(payload["status"]),
            barn_id=payload.get("barn_id"),
            certificate_pem=(
                decode_binary(payload["certificate_pem"])
                if payload.get("certificate_pem")
                else None
            ),
            ca_certificate_pem=(
                decode_binary(payload["ca_certificate_pem"])
                if payload.get("ca_certificate_pem")
                else None
            ),
            grant_public_key=(
                decode_binary(payload["grant_public_key"])
                if payload.get("grant_public_key")
                else None
            ),
            decided_at=payload.get("decided_at"),
        )
        if result.status is EnrolmentStatus.APPROVED:
            node.complete_enrolment(result)
        return result
