"""Coordinator public HTTPS API."""

from __future__ import annotations

from fastapi import FastAPI, Header

from .. import __version__
from ..api_models import (
    ChallengeRequest,
    ChallengeResponse,
    EnrolmentRequest,
    ReceiptResponse,
    ResultResponse,
    StatusResponse,
    decode_binary,
    encode_binary,
)
from ..errors import BarnError, ErrorCode
from ..http_common import install_http_safety
from ..models import EnrolmentSubmission
from .service import CoordinatorService


def _result_response(result: object) -> ResultResponse:
    return ResultResponse(
        request_id=result.request_id,
        status=result.status,
        barn_id=result.barn_id,
        certificate_pem=(
            encode_binary(result.certificate_pem) if result.certificate_pem else None
        ),
        ca_certificate_pem=(
            encode_binary(result.ca_certificate_pem)
            if result.ca_certificate_pem
            else None
        ),
        grant_public_key=(
            encode_binary(result.grant_public_key) if result.grant_public_key else None
        ),
        decided_at=result.decided_at,
    )


def create_public_app(service: CoordinatorService) -> FastAPI:
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
        receipt = service.submit_enrolment(
            request.invite_code.get_secret_value(), submission
        )
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

    return app
