"""JSON-safe models for public and loopback HTTP APIs."""

from __future__ import annotations

import base64
import binascii
from datetime import datetime
from uuid import UUID

from pydantic import Field, SecretStr

from .models import EnrolmentStatus, Heartbeat, NodeStatus, StrictModel


def encode_binary(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def decode_binary(value: str) -> bytes:
    try:
        return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Invalid base64url value") from exc


class ChallengeRequest(StrictModel):
    invite_code: SecretStr
    node_id: UUID


class ChallengeResponse(StrictModel):
    challenge: str
    expires_at: datetime


class EnrolmentRequest(StrictModel):
    invite_code: SecretStr
    node_id: UUID
    node_name: str
    advertised_host: str
    peer_port: int
    protocol_version: str
    identity_public_key: str
    csr_pem: str
    challenge: str
    proof: str


class ReceiptResponse(StrictModel):
    request_id: UUID
    receipt: str
    status: EnrolmentStatus


class ResultResponse(StrictModel):
    request_id: UUID
    status: EnrolmentStatus
    barn_id: UUID | None = None
    certificate_pem: str | None = None
    ca_certificate_pem: str | None = None
    grant_public_key: str | None = None
    decided_at: datetime | None = None


class InviteRequest(StrictModel):
    ttl_seconds: int = Field(ge=60, le=86400)


class InviteResponse(StrictModel):
    invite_id: str
    code: str
    expires_at: datetime


class PendingResponse(StrictModel):
    request_id: str
    node_id: str
    node_name: str
    advertised_host: str
    peer_port: int
    identity_fingerprint: str
    created_at: datetime


class StatusResponse(StrictModel):
    status: str
    version: str


class HeartbeatResponse(StrictModel):
    accepted_at: datetime
    status: NodeStatus


class NodeRecordResponse(StrictModel):
    node_id: UUID
    name: str
    status: NodeStatus
    peer_endpoint: str
    software_version: str | None = None
    storage_total: int | None = None
    storage_available: int | None = None
    last_seen_at: datetime | None = None


class RegistryResponse(StrictModel):
    generated_at: datetime
    nodes: list[NodeRecordResponse]


class ShareCreateRequest(StrictModel):
    file_id: UUID
    source_node_id: UUID
    recipient_node_id: UUID
    ttl_seconds: int = Field(ge=1, le=30 * 24 * 60 * 60)


class ShareResponse(StrictModel):
    share_id: UUID
    file_id: UUID
    source_node_id: UUID
    recipient_node_id: UUID
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None


class GrantResponse(StrictModel):
    grant_id: UUID
    share_id: UUID
    transfer_id: UUID
    file_id: UUID
    source_node_id: UUID
    recipient_node_id: UUID
    issued_at: datetime
    expires_at: datetime
    signature: str


class RelayTicketResponse(StrictModel):
    ticket_id: UUID
    barn_id: UUID
    source_node_id: UUID
    recipient_node_id: UUID
    issued_at: datetime
    expires_at: datetime
    signature: str


HeartbeatRequest = Heartbeat
