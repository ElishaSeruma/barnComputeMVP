"""CA-verified coordinator client for node enrolment."""

from __future__ import annotations

import json
import ssl
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from cryptography import x509
from cryptography.x509.oid import NameOID

from ..api_models import decode_binary, encode_binary
from ..auth import sign_request
from ..control_transport import parse_control_grant
from ..crypto import load_private_identity
from ..errors import BarnError, ErrorCode
from ..models import (
    EnrolmentChallenge,
    EnrolmentReceipt,
    EnrolmentResult,
    EnrolmentStatus,
    FileManifest,
    TransferGrant,
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
        relay_url: str | None = None,
        relay_ca: Path | None = None,
    ) -> None:
        if not base_url.startswith("https://") and transport is None:
            raise BarnError(ErrorCode.CONFIGURATION, "Coordinator URL must use HTTPS")
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            verify=ssl.create_default_context(cafile=str(ca_certificate))
            if transport is None
            else True,
            timeout=httpx.Timeout(timeout, connect=min(timeout, 5.0)),
            follow_redirects=False,
            transport=transport,
        )
        self.relay_url = relay_url
        self.relay_ca = relay_ca
        self.control = None

    def close(self) -> None:
        if self.control is not None:
            self.control.close()
            self.control = None
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

    def _request(
        self,
        node: NodeService,
        method: str,
        target: str,
        *,
        content: bytes = b"",
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        if self.control is not None:
            try:
                return self.control.request(method, target, headers or {}, content)
            except BarnError:
                self.control.close()
                self.control = None
        try:
            return self.client.request(method, target, content=content, headers=headers)
        except httpx.TransportError:
            if self.relay_url is None:
                raise
        from ..control_transport import ControlConnection

        if self.control is None:
            self.control = ControlConnection(self.relay_url, node, ca=self.relay_ca)
        try:
            return self.control.request(method, target, headers or {}, content)
        except BarnError:
            self.control.close()
            self.control = None
            raise

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
            control_grant=(
                parse_control_grant(payload["control_grant"])
                if payload.get("control_grant")
                else None
            ),
            decided_at=payload.get("decided_at"),
        )
        if result.status is EnrolmentStatus.APPROVED:
            node.complete_enrolment(result)
        return result

    @staticmethod
    def _signed_headers(node: NodeService, method: str, target: str, body: bytes) -> dict[str, str]:
        metadata = node.load_metadata()
        timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        nonce = uuid4().hex
        key = load_private_identity(node.state_dir / "secrets" / "identity-key.pem")
        return {
            "X-Barn-Node-ID": str(metadata.node_id),
            "X-Barn-Timestamp": timestamp,
            "X-Barn-Nonce": nonce,
            "X-Barn-Signature": sign_request(key, method, target, timestamp, nonce, body),
        }

    def send_heartbeat(self, node: NodeService) -> dict[str, object]:
        heartbeat = node.next_heartbeat()
        body = heartbeat.model_dump_json().encode("utf-8")
        target = "/v1/heartbeat"
        response = self._request(
            node,
            "POST",
            target,
            content=body,
            headers={
                **self._signed_headers(node, "POST", target, body),
                "Content-Type": "application/json",
            },
        )
        self._raise_for_error(response)
        return dict(response.json())

    def refresh_registry(self, node: NodeService) -> dict[str, object]:
        target = "/v1/nodes"
        response = self._request(
            node, "GET", target, headers=self._signed_headers(node, "GET", target, b"")
        )
        self._raise_for_error(response)
        payload = dict(response.json())
        node.store_registry(payload)
        return payload

    def signed(self, node: NodeService, method: str, target: str, payload: dict | None = None):
        body = json.dumps(payload, separators=(",", ":")).encode() if payload is not None else b""
        response = self._request(
            node,
            method,
            target,
            content=body,
            headers={
                **self._signed_headers(node, method, target, body),
                "Content-Type": "application/json",
            },
        )
        self._raise_for_error(response)
        return response.json() if response.content else None

    def refresh_control_grant(self, node: NodeService) -> dict[str, object]:
        target = "/v1/control/grant"
        response = self._request(
            node, "GET", target, headers=self._signed_headers(node, "GET", target, b"")
        )
        self._raise_for_error(response)
        payload = dict(response.json())
        node.store_control_grant(payload)
        return payload

    def peer_key(self, node: NodeService, peer_id: UUID) -> bytes:
        return decode_binary(
            self.signed(node, "GET", f"/v1/nodes/{peer_id}/identity")["identity_public_key"]
        )


class PeerClient:
    def __init__(
        self,
        base_url: str,
        ca_certificate: Path,
        *,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.injected_transport = transport is not None
        if not base_url.startswith("https://") and transport is None:
            raise BarnError(ErrorCode.CONFIGURATION, "Peer URL must use HTTPS")
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            verify=ssl.create_default_context(cafile=str(ca_certificate))
            if transport is None
            else True,
            timeout=httpx.Timeout(timeout, connect=min(timeout, 5.0)),
            follow_redirects=False,
            transport=transport,
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> PeerClient:
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
            message = f"Peer returned HTTP {response.status_code}"
        raise BarnError(code, message)

    @staticmethod
    def _grant_header(grant_payload: dict[str, object]) -> str:
        return encode_binary(json.dumps(grant_payload, separators=(",", ":")).encode())

    def download(
        self,
        node: NodeService,
        grant_payload: dict[str, object],
        destination: Path,
    ) -> Path:
        grant = TransferGrant(
            grant_id=grant_payload["grant_id"],
            share_id=grant_payload["share_id"],
            transfer_id=grant_payload["transfer_id"],
            file_id=grant_payload["file_id"],
            source_node_id=grant_payload["source_node_id"],
            recipient_node_id=grant_payload["recipient_node_id"],
            issued_at=grant_payload["issued_at"],
            expires_at=grant_payload["expires_at"],
            signature=decode_binary(str(grant_payload["signature"])),
        )
        target = f"/v1/files/{grant.file_id}/manifest"
        header = {"X-Barn-Transfer-Grant": self._grant_header(grant_payload)}
        response = self.client.get(
            target,
            headers={**header, **CoordinatorClient._signed_headers(node, "GET", target, b"")},
        )
        self._raise_for_error(response)
        if not self.injected_transport:
            stream = response.extensions.get("network_stream")
            tls = stream.get_extra_info("ssl_object") if stream else None
            certificate = (
                x509.load_der_x509_certificate(tls.getpeercert(True)) if tls else None
            )
            identifiers = (
                certificate.subject.get_attributes_for_oid(NameOID.ORGANIZATIONAL_UNIT_NAME)
                if certificate
                else []
            )
            if len(identifiers) != 1 or identifiers[0].value != str(grant.source_node_id):
                raise BarnError(
                    ErrorCode.NOT_AUTHENTICATED, "TLS peer identity differs from source"
                )
        manifest = FileManifest.model_validate(response.json())
        journal = node.start_transfer(grant, manifest)
        for chunk in manifest.chunks:
            if chunk.index in journal.completed_chunks:
                continue
            target = f"/v1/files/{grant.file_id}/chunks/{chunk.index}"
            with self.client.stream(
                "GET",
                target,
                headers={**header, **CoordinatorClient._signed_headers(node, "GET", target, b"")},
            ) as response:
                if not response.is_success:
                    response.read()
                    self._raise_for_error(response)
                payload = bytearray()
                for block in response.iter_bytes(64 * 1024):
                    payload.extend(block)
                    if len(payload) > chunk.length:
                        raise BarnError(ErrorCode.INVALID_REQUEST, "Peer chunk exceeds manifest")
            journal = node.accept_transfer_chunk(grant, manifest, chunk.index, bytes(payload))
        return node.export_transfer(grant, manifest, destination)
