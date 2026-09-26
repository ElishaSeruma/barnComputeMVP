"""Versioned protocol and metadata models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

PROTOCOL_VERSION = "1.0"
CHUNK_SIZE = 1024 * 1024
MAX_FILE_SIZE = 512 * 1024 * 1024


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NodeStatus(StrEnum):
    UNREGISTERED = "UNREGISTERED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    ONLINE = "ONLINE"
    SUSPECT = "SUSPECT"
    OFFLINE = "OFFLINE"
    REVOKED = "REVOKED"


class TransportMode(StrEnum):
    AUTO = "auto"
    DIRECT = "direct"
    RELAY = "relay"


class EnrolmentStatus(StrEnum):
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class EnrolmentChallenge(StrictModel):
    challenge: str = Field(min_length=32, max_length=256)
    expires_at: datetime


class EnrolmentSubmission(StrictModel):
    node_id: UUID
    node_name: str = Field(min_length=1, max_length=100)
    advertised_host: str = Field(min_length=1, max_length=253)
    peer_port: int = Field(ge=1, le=65535)
    protocol_version: str = PROTOCOL_VERSION
    identity_public_key: bytes = Field(min_length=32, max_length=32)
    csr_pem: bytes = Field(min_length=64, max_length=16384)
    challenge: str = Field(min_length=32, max_length=256)
    proof: bytes = Field(min_length=64, max_length=64)


class EnrolmentReceipt(StrictModel):
    request_id: UUID
    receipt: str = Field(min_length=32, max_length=256)
    status: EnrolmentStatus


class EnrolmentResult(StrictModel):
    request_id: UUID
    status: EnrolmentStatus
    barn_id: UUID | None = None
    certificate_pem: bytes | None = None
    ca_certificate_pem: bytes | None = None
    grant_public_key: bytes | None = None
    decided_at: datetime | None = None


class ChunkManifest(StrictModel):
    index: int = Field(ge=0)
    offset: int = Field(ge=0)
    length: int = Field(ge=0, le=CHUNK_SIZE)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class FileManifest(StrictModel):
    protocol_version: str = PROTOCOL_VERSION
    file_id: UUID
    owner_node_id: UUID
    display_name: str = Field(min_length=1, max_length=255)
    size: int = Field(ge=0, le=MAX_FILE_SIZE)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_size: int = Field(default=CHUNK_SIZE, ge=1, le=CHUNK_SIZE)
    chunks: tuple[ChunkManifest, ...]
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("created_at must be timezone-aware UTC")
        return value

    @field_validator("chunks")
    @classmethod
    def require_ordered_chunks(cls, value: tuple[ChunkManifest, ...]) -> tuple[ChunkManifest, ...]:
        for expected, chunk in enumerate(value):
            if chunk.index != expected:
                raise ValueError("chunk indexes must be contiguous and start at zero")
            if chunk.offset != expected * CHUNK_SIZE:
                raise ValueError("chunk offsets must follow the fixed chunk size")
        return value


class FileShare(StrictModel):
    share_id: UUID
    file_id: UUID
    source_node_id: UUID
    recipient_node_id: UUID
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None


class TransferGrant(StrictModel):
    grant_id: UUID
    share_id: UUID
    transfer_id: UUID
    file_id: UUID
    source_node_id: UUID
    recipient_node_id: UUID
    issued_at: datetime
    expires_at: datetime
    signature: bytes = Field(min_length=64, max_length=64)


class TransferJournal(StrictModel):
    transfer_id: UUID
    file_id: UUID
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    completed_chunks: tuple[int, ...] = ()


class RelayTicket(StrictModel):
    ticket_id: UUID
    barn_id: UUID
    source_node_id: UUID
    recipient_node_id: UUID
    issued_at: datetime
    expires_at: datetime
    signature: bytes = Field(min_length=64, max_length=64)

class Heartbeat(StrictModel):
    protocol_version: str = PROTOCOL_VERSION
    node_id: UUID
    boot_epoch: UUID
    sequence: int = Field(ge=1)
    peer_endpoint: str
    software_version: str
    storage_total: int = Field(ge=0)
    storage_available: int = Field(ge=0)
    sent_at: datetime
