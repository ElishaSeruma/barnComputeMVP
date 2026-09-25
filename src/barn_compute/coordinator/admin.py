"""Loopback-only coordinator administration API."""

from __future__ import annotations

import secrets
from dataclasses import asdict
from datetime import timedelta

from fastapi import Depends, FastAPI, Header

from .. import __version__
from ..api_models import (
    InviteRequest,
    InviteResponse,
    PendingResponse,
    ResultResponse,
    StatusResponse,
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

    return app
