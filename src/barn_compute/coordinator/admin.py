"""Loopback-only coordinator administration API."""

from __future__ import annotations

import secrets
from dataclasses import asdict
from datetime import timedelta
from uuid import UUID

from fastapi import Depends, FastAPI, Header

from .. import __version__
from ..api_models import (
    GrantResponse,
    InviteRequest,
    InviteResponse,
    PendingResponse,
    RelayTicketResponse,
    ResultResponse,
    ShareCreateRequest,
    ShareResponse,
    StatusResponse,
    encode_binary,
)
from ..errors import BarnError, ErrorCode
from ..http_common import install_http_safety
from .app import _result_response
from .service import CoordinatorService


def create_admin_app(service: CoordinatorService, admin_token: str) -> FastAPI:
    app = FastAPI(title="barnCompute coordinator admin", version=__version__)
    install_http_safety(app)

    def require_admin(authorization: str | None = Header(None)) -> None:
        scheme, separator, supplied = (authorization or "").partition(" ")
        if (
            not separator
            or scheme.lower() != "bearer"
            or not secrets.compare_digest(supplied, admin_token)
        ):
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Admin token is invalid")

    @app.get("/local/v1/status", response_model=StatusResponse)
    async def status(_admin: None = Depends(require_admin)) -> StatusResponse:
        service.load_metadata()
        return StatusResponse(status="ok", version=__version__)

    @app.post("/local/v1/invites", response_model=InviteResponse)
    async def create_invite(
        request: InviteRequest,
        _admin: None = Depends(require_admin),
    ) -> InviteResponse:
        invite = service.create_invite(timedelta(seconds=request.ttl_seconds))
        return InviteResponse(
            invite_id=invite.invite_id,
            code=invite.code,
            expires_at=invite.expires_at,
        )

    @app.get("/local/v1/enrolments", response_model=list[PendingResponse])
    async def pending(_admin: None = Depends(require_admin)) -> list[PendingResponse]:
        return [PendingResponse(**asdict(item)) for item in service.list_pending_enrolments()]

    @app.post(
        "/local/v1/enrolments/{request_id}/approve",
        response_model=ResultResponse,
    )
    async def approve(
        request_id: str,
        _admin: None = Depends(require_admin),
    ) -> ResultResponse:
        return _result_response(service.approve_enrolment(request_id))

    @app.post("/local/v1/enrolments/{request_id}/reject", status_code=204)
    async def reject(
        request_id: str,
        _admin: None = Depends(require_admin),
    ) -> None:
        service.reject_enrolment(request_id)

    @app.post("/local/v1/shares", response_model=ShareResponse)
    async def create_share(
        request: ShareCreateRequest,
        _admin: None = Depends(require_admin),
    ) -> ShareResponse:
        share = service.create_share(
            request.file_id,
            request.source_node_id,
            request.recipient_node_id,
            timedelta(seconds=request.ttl_seconds),
        )
        return ShareResponse(**share.model_dump())

    @app.get("/local/v1/shares", response_model=list[ShareResponse])
    async def list_shares(_admin: None = Depends(require_admin)) -> list[ShareResponse]:
        return [ShareResponse(**share.model_dump()) for share in service.list_shares()]

    @app.post("/local/v1/shares/{share_id}/revoke", status_code=204)
    async def revoke_share(
        share_id: str,
        _admin: None = Depends(require_admin),
    ) -> None:
        service.revoke_share(UUID(share_id))

    @app.post("/local/v1/shares/{share_id}/grant", response_model=GrantResponse)
    async def issue_grant(
        share_id: str,
        recipient_node_id: str,
        _admin: None = Depends(require_admin),
    ) -> GrantResponse:
        grant = service.issue_transfer_grant(
            UUID(share_id), UUID(recipient_node_id)
        )
        return GrantResponse(
            **grant.model_dump(exclude={"signature"}), signature=encode_binary(grant.signature)
        )

    @app.post("/local/v1/relay/tickets", response_model=RelayTicketResponse)
    async def issue_relay_ticket(
        source_node_id: str,
        recipient_node_id: str,
        ttl_seconds: int = 300,
        _admin: None = Depends(require_admin),
    ) -> RelayTicketResponse:
        ticket = service.issue_relay_ticket(
            UUID(source_node_id), UUID(recipient_node_id), ttl=timedelta(seconds=ttl_seconds)
        )
        return RelayTicketResponse(
            **ticket.model_dump(exclude={"signature"}),
            signature=encode_binary(ticket.signature),
        )

    return app
