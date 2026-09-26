"""Node peer and loopback status APIs."""

from __future__ import annotations

import json
import secrets

from fastapi import Depends, FastAPI, Header, Response

from .. import __version__
from ..api_models import StatusResponse, decode_binary
from ..errors import BarnError, ErrorCode
from ..http_common import install_http_safety
from ..models import FileManifest, NodeStatus, TransferGrant
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

    def grant_from_header(value: str | None) -> TransferGrant:
        if not value:
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Transfer grant is required")
        try:
            payload = json.loads(decode_binary(value))
            payload["signature"] = decode_binary(payload["signature"])
            return TransferGrant.model_validate(payload)
        except (ValueError, TypeError) as exc:
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Transfer grant is invalid") from exc

    @app.get("/v1/files/{file_id}/manifest", response_model=FileManifest)
    async def manifest(
        file_id: str,
        x_barn_transfer_grant: str | None = Header(None),
    ) -> FileManifest:
        grant = grant_from_header(x_barn_transfer_grant)
        if str(grant.file_id) != file_id:
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Grant file scope is invalid")
        try:
            return next(item for item in service.list_files() if item.file_id == grant.file_id)
        except StopIteration as exc:
            raise BarnError(ErrorCode.INVALID_REQUEST, "Managed file is unavailable") from exc

    @app.get("/v1/files/{file_id}/chunks/{index}")
    async def chunk(
        file_id: str,
        index: int,
        x_barn_transfer_grant: str | None = Header(None),
    ) -> Response:
        grant = grant_from_header(x_barn_transfer_grant)
        if str(grant.file_id) != file_id:
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Grant file scope is invalid")
        return Response(
            service.read_grant_chunk(grant, index), media_type="application/octet-stream"
        )

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
