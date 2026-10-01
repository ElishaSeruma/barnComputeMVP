"""Coordinator public HTTPS API."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends, FastAPI, Header, Request
from pydantic import ValidationError

from .. import __version__
from ..api_models import (
    ChallengeRequest,
    ChallengeResponse,
    EnrolmentRequest,
    HeartbeatRequest,
    HeartbeatResponse,
    NodeRecordResponse,
    ReceiptResponse,
    RegistryResponse,
    ResultResponse,
    ShareCreateRequest,
    StatusResponse,
    decode_binary,
    encode_binary,
)
from ..auth import SignedRequest
from ..errors import BarnError, ErrorCode
from ..http_common import install_http_safety
from ..models import EnrolmentSubmission
from .repository import CoordinatorRepository
from .service import CoordinatorService


def _result_response(result: object) -> ResultResponse:
    control_grant = None
    if result.control_grant:
        control_grant = result.control_grant.model_dump(mode="json", exclude={"signature"})
        control_grant["signature"] = encode_binary(result.control_grant.signature)
    return ResultResponse(
        request_id=result.request_id,
        status=result.status,
        barn_id=result.barn_id,
        certificate_pem=(encode_binary(result.certificate_pem) if result.certificate_pem else None),
        ca_certificate_pem=(
            encode_binary(result.ca_certificate_pem) if result.ca_certificate_pem else None
        ),
        grant_public_key=(
            encode_binary(result.grant_public_key) if result.grant_public_key else None
        ),
        control_grant=control_grant,
        decided_at=result.decided_at,
    )


def create_public_app(service: CoordinatorService) -> FastAPI:
    with CoordinatorRepository(service.database_path) as repository:
        repository.migrate()
    app = FastAPI(title="barnCompute coordinator", version=__version__)
    install_http_safety(app)

    @app.get("/v1/health", response_model=StatusResponse)
    async def health() -> StatusResponse:
        service.load_metadata()
        return StatusResponse(status="ok", version=__version__)

    @app.post("/v1/enrolments/challenge", response_model=ChallengeResponse)
    async def challenge(request: ChallengeRequest) -> ChallengeResponse:
        issued = service.create_enrolment_challenge(
            request.invite_code.get_secret_value(), str(request.node_id)
        )
        return ChallengeResponse(
            challenge=issued.challenge,
            expires_at=issued.expires_at,
        )

    @app.post("/v1/enrolments", response_model=ReceiptResponse, status_code=202)
    async def submit(request: EnrolmentRequest) -> ReceiptResponse:
        try:
            submission = EnrolmentSubmission(
                node_id=request.node_id,
                node_name=request.node_name,
                advertised_host=request.advertised_host,
                peer_port=request.peer_port,
                protocol_version=request.protocol_version,
                identity_public_key=decode_binary(request.identity_public_key),
                csr_pem=decode_binary(request.csr_pem),
                challenge=request.challenge,
                proof=decode_binary(request.proof),
            )
        except ValueError as exc:
            raise BarnError(ErrorCode.INVALID_REQUEST, "Enrolment encoding is invalid") from exc
        receipt = service.submit_enrolment(request.invite_code.get_secret_value(), submission)
        return ReceiptResponse(
            request_id=receipt.request_id,
            receipt=receipt.receipt,
            status=receipt.status,
        )

    @app.get("/v1/enrolments/{request_id}", response_model=ResultResponse)
    async def result(
        request_id: str,
        x_barn_enrolment_receipt: str | None = Header(None),
    ) -> ResultResponse:
        if not x_barn_enrolment_receipt:
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Enrolment receipt is required")
        enrolment = service.poll_enrolment(x_barn_enrolment_receipt)
        if str(enrolment.request_id) != request_id:
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Enrolment receipt is invalid")
        return _result_response(enrolment)

    def signed_request(
        request: Request,
        body: bytes,
        timestamp: str | None,
        nonce: str | None,
        signature: str | None,
    ) -> SignedRequest:
        if not all((timestamp, nonce, signature)):
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Signed request headers are required")
        return SignedRequest(
            method=request.method,
            target=request.url.path + (f"?{request.url.query}" if request.url.query else ""),
            timestamp=timestamp,
            nonce=nonce,
            signature=signature,
            body=body,
        )

    @app.post("/v1/heartbeat", response_model=HeartbeatResponse)
    async def heartbeat(
        request: Request,
        x_barn_timestamp: str | None = Header(None),
        x_barn_nonce: str | None = Header(None),
        x_barn_signature: str | None = Header(None),
    ) -> HeartbeatResponse:
        body = await request.body()
        try:
            value = HeartbeatRequest.model_validate_json(body)
        except ValidationError as exc:
            raise BarnError(ErrorCode.INVALID_REQUEST, "Heartbeat is invalid") from exc
        accepted_at = service.accept_heartbeat(
            value,
            signed_request(request, body, x_barn_timestamp, x_barn_nonce, x_barn_signature),
        )
        return HeartbeatResponse(accepted_at=accepted_at, status="ONLINE")

    @app.get("/v1/nodes", response_model=RegistryResponse)
    async def nodes(
        request: Request,
        x_barn_node_id: str | None = Header(None),
        x_barn_timestamp: str | None = Header(None),
        x_barn_nonce: str | None = Header(None),
        x_barn_signature: str | None = Header(None),
    ) -> RegistryResponse:
        if not x_barn_node_id:
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Node ID is required")
        generated_at = datetime.now(UTC)
        records = service.list_registered_nodes(
            x_barn_node_id,
            signed_request(request, b"", x_barn_timestamp, x_barn_nonce, x_barn_signature),
            now=generated_at,
        )
        return RegistryResponse(
            generated_at=generated_at,
            nodes=[NodeRecordResponse(**asdict(record)) for record in records],
        )

    async def member(request: Request) -> UUID:
        headers = request.headers
        try:
            node_id = UUID(headers.get("x-barn-node-id", ""))
        except ValueError as exc:
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Node identity is required") from exc
        service._authenticate_node(
            str(node_id),
            signed_request(
                request,
                await request.body(),
                headers.get("x-barn-timestamp"),
                headers.get("x-barn-nonce"),
                headers.get("x-barn-signature"),
            ),
            now=datetime.now(UTC),
        )
        return node_id

    def wire(value: object) -> dict:
        payload = value.model_dump(mode="json", exclude={"signature"})
        payload["signature"] = encode_binary(value.signature)
        return payload

    @app.post("/v1/shares")
    async def create_share(value: ShareCreateRequest, node_id: UUID = Depends(member)) -> dict:
        from datetime import timedelta

        if value.source_node_id != node_id:
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Only the source may create a share")
        return service.create_share(
            value.file_id, node_id, value.recipient_node_id, timedelta(seconds=value.ttl_seconds)
        ).model_dump(mode="json")

    @app.get("/v1/shares")
    async def inbox(node_id: UUID = Depends(member)) -> list[dict]:
        return [
            value.model_dump(mode="json")
            for value in service.list_shares()
            if node_id in (value.source_node_id, value.recipient_node_id)
        ]

    @app.post("/v1/shares/{share_id}/grant")
    async def grant(share_id: UUID, node_id: UUID = Depends(member)) -> dict:
        return wire(service.issue_transfer_grant(share_id, node_id))

    @app.post("/v1/shares/{share_id}/revoke", status_code=204)
    async def revoke(share_id: UUID, node_id: UUID = Depends(member)) -> None:
        shares = service.list_shares()
        if not any(s.share_id == share_id and s.source_node_id == node_id for s in shares):
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Only the source may revoke a share")
        service.revoke_share(share_id)

    @app.post("/v1/grants/validate")
    async def validate_grant(request: Request, node_id: UUID = Depends(member)) -> dict:
        from ..models import TransferGrant

        payload = await request.json()
        payload["signature"] = decode_binary(payload["signature"])
        supplied = TransferGrant.model_validate(payload)
        if node_id not in (supplied.source_node_id, supplied.recipient_node_id):
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Grant peer scope is invalid")
        # Recheck current share and both membership records on every delivery.
        current = service.issue_transfer_grant(supplied.share_id, supplied.recipient_node_id)
        if (current.file_id, current.source_node_id) != (supplied.file_id, supplied.source_node_id):
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Grant scope is invalid")
        return {"valid": True}

    @app.get("/v1/nodes/{peer_id}/identity")
    async def identity(peer_id: UUID, node_id: UUID = Depends(member)) -> dict:
        with CoordinatorRepository(service.database_path) as repository:
            peer = repository.get_node(str(peer_id))
        if peer is None or peer["status"] == "REVOKED":
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Peer is unavailable")
        return {
            "node_id": str(peer_id),
            "identity_public_key": encode_binary(peer["identity_public_key"]),
        }

    @app.get("/v1/control/grant")
    async def control_grant(node_id: UUID = Depends(member)) -> dict:
        return wire(service.issue_control_grant(node_id))

    @app.post("/v1/shares/{share_id}/relay-ticket")
    async def relay_ticket(share_id: UUID, node_id: UUID = Depends(member)) -> dict:
        import json

        grant = service.issue_transfer_grant(share_id, node_id)
        ticket = service.issue_relay_ticket(grant.source_node_id, node_id)
        payload = wire(ticket)
        with CoordinatorRepository(service.database_path) as repository, repository.connection:
            repository.connection.execute(
                "DELETE FROM relay_tickets WHERE expires_at < ?",
                (datetime.now(UTC).isoformat(),),
            )
            repository.connection.execute(
                "INSERT INTO relay_tickets VALUES (?, ?, ?, ?)",
                (
                    str(ticket.ticket_id),
                    str(ticket.source_node_id),
                    ticket.expires_at.isoformat(),
                    json.dumps(payload),
                ),
            )
        return payload

    @app.get("/v1/relay/tickets")
    async def relay_inbox(node_id: UUID = Depends(member)) -> list[dict]:
        import json

        with CoordinatorRepository(service.database_path) as repository:
            rows = repository.connection.execute(
                "SELECT payload FROM relay_tickets WHERE source_node_id = ? AND expires_at > ?",
                (str(node_id), datetime.now(UTC).isoformat()),
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    return app
