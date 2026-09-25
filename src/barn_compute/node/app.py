"""Node peer and loopback status APIs."""

from __future__ import annotations

import secrets

from fastapi import Depends, FastAPI, Header

from .. import __version__
from ..api_models import StatusResponse
from ..errors import BarnError, ErrorCode
from ..http_common import install_http_safety
from ..models import NodeStatus
from .service import NodeService


def create_peer_app(service: NodeService) -> FastAPI:
    app = FastAPI(title="barnCompute node peer", version=__version__)
    install_http_safety(app)

    @app.get("/v1/health", response_model=StatusResponse)
    async def health() -> StatusResponse:
        metadata = service.load_metadata()
        if metadata.status not in (
            NodeStatus.APPROVED,
            NodeStatus.ONLINE,
            NodeStatus.SUSPECT,
            NodeStatus.OFFLINE,
        ):
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Node is not approved")
        return StatusResponse(status=metadata.status, version=__version__)

    return app


def create_local_app(service: NodeService, admin_token: str) -> FastAPI:
    app = FastAPI(title="barnCompute node local", version=__version__)
    install_http_safety(app)

    def require_admin(authorization: str | None = Header(None)) -> None:
        scheme, separator, supplied = (authorization or "").partition(" ")
        if (
            not separator
            or scheme.lower() != "bearer"
            or not secrets.compare_digest(supplied, admin_token)
        ):
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Local token is invalid")

    @app.get("/local/v1/status", response_model=StatusResponse)
    async def status(_admin: None = Depends(require_admin)) -> StatusResponse:
        metadata = service.load_metadata()
        return StatusResponse(status=metadata.status, version=__version__)

    return app
