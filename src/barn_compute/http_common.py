"""Shared HTTP error handling and request-size controls."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .errors import BarnError, ErrorCode

MAX_JSON_BODY = 64 * 1024

ERROR_STATUS = {
    ErrorCode.INVALID_REQUEST: 400,
    ErrorCode.CONFIGURATION: 400,
    ErrorCode.NOT_AUTHENTICATED: 401,
    ErrorCode.NOT_AUTHORISED: 403,
    ErrorCode.REPLAY_DETECTED: 409,
    ErrorCode.CLOCK_SKEW: 401,
    ErrorCode.PROTOCOL_MISMATCH: 409,
    ErrorCode.NOT_IMPLEMENTED: 501,
}


class RequestSizeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.windows: dict[str, tuple[float, int]] = {}

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        now = time.monotonic()
        address = request.client.host if request.client else "unknown"
        self.windows = {host: entry for host, entry in self.windows.items() if now - entry[0] < 60}
        started, count = self.windows.get(address, (now, 0))
        if count >= 1200 or (address not in self.windows and len(self.windows) >= 1024):
            return JSONResponse(
                status_code=429,
                content={
                    "error": {"code": "INVALID_REQUEST", "message": "Request rate limit exceeded"}
                },
            )
        self.windows[address] = (started, count + 1)
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > MAX_JSON_BODY:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": "PAYLOAD_TOO_LARGE",
                                "message": "Request body is too large",
                                "request_id": str(uuid4()),
                            }
                        },
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": {
                            "code": "INVALID_REQUEST",
                            "message": "Invalid Content-Length",
                            "request_id": str(uuid4()),
                        }
                    },
                )
        chunks = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_JSON_BODY:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "PAYLOAD_TOO_LARGE",
                            "message": "Request body is too large",
                        }
                    },
                )
            chunks.append(chunk)
        request._body = b"".join(chunks)
        return await call_next(request)


def install_http_safety(app: FastAPI) -> None:
    app.add_middleware(RequestSizeMiddleware)

    @app.exception_handler(BarnError)
    async def barn_error_handler(_request: Request, exc: BarnError) -> JSONResponse:
        return JSONResponse(
            status_code=ERROR_STATUS.get(exc.code, 500),
            content={
                "error": {
                    "code": str(exc.code),
                    "message": exc.message,
                    "request_id": str(uuid4()),
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Request validation failed",
                    "request_id": str(uuid4()),
                }
            },
        )
