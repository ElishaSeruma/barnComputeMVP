"""Coordinator initialization and invitation lifecycle."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import NameOID
from pydantic import BaseModel, ConfigDict

from ..auth import NonceStore, SignedRequest, verify_request
from ..config import ensure_private_directory, write_private_bytes, write_private_json
from ..crypto import (
    certificate_fingerprint,
    certificate_san_matches,
    create_barn_ca,
    create_server_certificate,
    generate_identity,
    issue_node_certificate,
    load_certificate,
    load_private_identity,
    load_public_key,
    public_key_bytes,
    public_key_fingerprint,
    save_certificate,
    save_private_identity,
)
from ..errors import BarnError, ErrorCode
from ..grants import canonical_relay_ticket, canonical_transfer_grant
from ..models import (
    PROTOCOL_VERSION,
    EnrolmentChallenge,
    EnrolmentReceipt,
    EnrolmentResult,
    EnrolmentStatus,
    EnrolmentSubmission,
    FileShare,
    Heartbeat,
    NodeStatus,
    RelayTicket,
    TransferGrant,
)
from ..node.service import canonical_enrolment_proof
from .repository import CoordinatorRepository


class CoordinatorMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    barn_id: UUID
    name: str
    advertised_host: str
    created_at: datetime
    ca_fingerprint: str


@dataclass(frozen=True, slots=True)
class CreatedInvite:
    invite_id: str
    code: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class PendingEnrolment:
    request_id: str
    node_id: str
    node_name: str
    advertised_host: str
    peer_port: int
    identity_fingerprint: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RegisteredNode:
    node_id: str
    name: str
    status: NodeStatus
    peer_endpoint: str
    software_version: str | None
    storage_total: int | None
    storage_available: int | None
    last_seen_at: datetime | None


def _validate_name(name: str) -> str:
    clean = name.strip()
    if not clean or len(clean) > 100 or any(ord(character) < 32 for character in clean):
        raise BarnError(ErrorCode.INVALID_REQUEST, "Barn name must be 1-100 printable characters")
    return clean


def _invite_digest(code: str) -> bytes:
    return hashlib.sha256(code.encode("ascii")).digest()


def _secret_digest(value: str) -> bytes:
    return hashlib.sha256(value.encode("ascii")).digest()


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)


class CoordinatorService:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir.expanduser().resolve()

    @property
    def metadata_path(self) -> Path:
        return self.state_dir / "coordinator.json"

    @property
    def database_path(self) -> Path:
        return self.state_dir / "coordinator.db"

    def initialize(self, name: str, advertised_host: str) -> CoordinatorMetadata:
        name = _validate_name(name)
        advertised_host = advertised_host.strip()
        if (
            not advertised_host
            or len(advertised_host) > 253
            or any(character.isspace() for character in advertised_host)
        ):
            raise BarnError(ErrorCode.INVALID_REQUEST, "Advertised host is invalid")
        if self.state_dir.exists():
            raise BarnError(
                ErrorCode.CONFIGURATION,
                f"Coordinator state already exists at {self.state_dir}",
            )

        ensure_private_directory(self.state_dir.parent)
        staging = self.state_dir.parent / f".{self.state_dir.name}.init-{uuid4().hex}"
        ensure_private_directory(staging)
        try:
            barn_id = str(uuid4())
            created_at = datetime.now(UTC)
            ca_key, ca_certificate = create_barn_ca(barn_id, name)
            server_key, server_certificate = create_server_certificate(
                ca_key,
                ca_certificate,
                f"{name} coordinator",
                advertised_host,
            )
            grant_key = generate_identity()

            save_private_identity(ca_key, staging / "secrets" / "ca-key.pem")
            save_private_identity(server_key, staging / "secrets" / "coordinator-key.pem")
            save_private_identity(grant_key, staging / "secrets" / "grant-key.pem")
            save_certificate(ca_certificate, staging / "ca-cert.pem")
            save_certificate(server_certificate, staging / "coordinator-cert.pem")
            write_private_bytes(
                staging / "secrets" / "admin.token",
                (secrets.token_urlsafe(32) + "\n").encode("ascii"),
            )

            metadata = CoordinatorMetadata(
                barn_id=barn_id,
                name=name,
                advertised_host=advertised_host,
                created_at=created_at,
                ca_fingerprint=certificate_fingerprint(ca_certificate),
            )
            write_private_json(staging / "coordinator.json", metadata.model_dump(mode="json"))
            with CoordinatorRepository(staging / "coordinator.db") as repository:
                repository.migrate()
                repository.add_barn(
                    barn_id,
                    name,
                    advertised_host,
                    created_at.isoformat(),
                )
            os.replace(staging, self.state_dir)
            return metadata
        except Exception:
            if staging.exists():
                shutil.rmtree(staging)
            raise

    def load_metadata(self) -> CoordinatorMetadata:
        if not self.metadata_path.exists():
            raise BarnError(
                ErrorCode.CONFIGURATION,
                f"Coordinator is not initialized at {self.state_dir}",
            )
        try:
            return CoordinatorMetadata.model_validate_json(
                self.metadata_path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise BarnError(ErrorCode.CONFIGURATION, "Coordinator metadata is invalid") from exc

    def export_ca(self, output: Path) -> str:
        certificate = load_certificate(self.state_dir / "ca-cert.pem")
        if output.exists():
            raise BarnError(ErrorCode.CONFIGURATION, f"Output already exists: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
        return certificate_fingerprint(certificate)

    def create_invite(self, ttl: timedelta) -> CreatedInvite:
        self.load_metadata()
        if ttl < timedelta(minutes=1) or ttl > timedelta(hours=24):
            raise BarnError(ErrorCode.INVALID_REQUEST, "Invite TTL must be between 1m and 24h")
        created_at = datetime.now(UTC)
        invite = CreatedInvite(
            invite_id=str(uuid4()),
            code=secrets.token_urlsafe(24),
            expires_at=created_at + ttl,
        )
        with CoordinatorRepository(self.database_path) as repository:
            repository.add_invite(
                invite.invite_id,
                _invite_digest(invite.code),
                created_at.isoformat(),
                invite.expires_at.isoformat(),
            )
        return invite

    def create_enrolment_challenge(
        self,
        invite_code: str,
        node_id: str,
        *,
        ttl: timedelta = timedelta(minutes=5),
        now: datetime | None = None,
    ) -> EnrolmentChallenge:
        self.load_metadata()
        checked_at = now or datetime.now(UTC)
        try:
            UUID(node_id)
        except ValueError as exc:
            raise BarnError(ErrorCode.INVALID_REQUEST, "Node ID is invalid") from exc
        if ttl <= timedelta(0) or ttl > timedelta(minutes=10):
            raise BarnError(ErrorCode.INVALID_REQUEST, "Challenge TTL must be at most 10m")
        with CoordinatorRepository(self.database_path) as repository:
            invite = repository.get_invite_by_digest(_invite_digest(invite_code))
            if invite is None:
                raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Invitation is invalid")
            if invite["consumed_at"] is not None:
                raise BarnError(ErrorCode.NOT_AUTHORISED, "Invitation was already used")
            if _utc(invite["expires_at"]) <= checked_at:
                raise BarnError(ErrorCode.NOT_AUTHORISED, "Invitation has expired")
            if repository.invite_has_active_request(invite["invite_id"]):
                raise BarnError(ErrorCode.NOT_AUTHORISED, "Invitation is already reserved")
            challenge = secrets.token_urlsafe(32)
            expires_at = checked_at + ttl
            repository.add_challenge(
                str(uuid4()),
                invite["invite_id"],
                node_id,
                _secret_digest(challenge),
                checked_at.isoformat(),
                expires_at.isoformat(),
            )
        return EnrolmentChallenge(challenge=challenge, expires_at=expires_at)

    def submit_enrolment(
        self,
        invite_code: str,
        submission: EnrolmentSubmission,
        *,
        now: datetime | None = None,
    ) -> EnrolmentReceipt:
        self.load_metadata()
        checked_at = now or datetime.now(UTC)
        if submission.protocol_version.split(".", 1)[0] != PROTOCOL_VERSION.split(".", 1)[0]:
            raise BarnError(ErrorCode.PROTOCOL_MISMATCH, "Unsupported protocol major version")
        try:
            identity_key = load_public_key(submission.identity_public_key)
            identity_key.verify(
                submission.proof,
                canonical_enrolment_proof(
                    submission.challenge,
                    submission.node_id,
                    submission.csr_pem,
                    submission.advertised_host,
                    submission.peer_port,
                    submission.protocol_version,
                ),
            )
        except (InvalidSignature, ValueError) as exc:
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Identity proof is invalid") from exc

        try:
            csr = x509.load_pem_x509_csr(submission.csr_pem)
            if not csr.is_signature_valid:
                raise ValueError("CSR signature is invalid")
            if not certificate_san_matches(csr, submission.advertised_host):
                raise ValueError("CSR SAN does not match advertised host")
            organisational_unit = csr.subject.get_attributes_for_oid(
                NameOID.ORGANIZATIONAL_UNIT_NAME
            )
            common_name = csr.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
            if [item.value for item in organisational_unit] != [str(submission.node_id)]:
                raise ValueError("CSR Node ID does not match")
            if [item.value for item in common_name] != [submission.node_name]:
                raise ValueError("CSR node name does not match")
        except (ValueError, x509.ExtensionNotFound) as exc:
            raise BarnError(ErrorCode.INVALID_REQUEST, f"CSR is invalid: {exc}") from exc

        challenge_digest = _secret_digest(submission.challenge)
        receipt = secrets.token_urlsafe(32)
        request_id = uuid4()
        with CoordinatorRepository(self.database_path) as repository:
            invite = repository.get_invite_by_digest(_invite_digest(invite_code))
            challenge = repository.get_challenge_by_digest(challenge_digest)
            if invite is None or challenge is None:
                raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Invitation or challenge is invalid")
            if challenge["invite_id"] != invite["invite_id"]:
                raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Challenge is for another invitation")
            if challenge["node_id"] != str(submission.node_id):
                raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Challenge is for another node")
            if challenge["used_at"] is not None:
                raise BarnError(ErrorCode.NOT_AUTHORISED, "Challenge was already used")
            if invite["consumed_at"] is not None:
                raise BarnError(ErrorCode.NOT_AUTHORISED, "Invitation was already used")
            if _utc(invite["expires_at"]) <= checked_at:
                raise BarnError(ErrorCode.NOT_AUTHORISED, "Invitation has expired")
            if _utc(challenge["expires_at"]) <= checked_at:
                raise BarnError(ErrorCode.NOT_AUTHORISED, "Challenge has expired")
            if repository.invite_has_active_request(invite["invite_id"]):
                raise BarnError(ErrorCode.NOT_AUTHORISED, "Invitation is already reserved")
            existing_node = repository.get_node(str(submission.node_id))
            existing_request = repository.get_enrolment_by_node(str(submission.node_id))
            for existing in (existing_node, existing_request):
                if existing is not None:
                    if existing["identity_public_key"] != submission.identity_public_key:
                        raise BarnError(
                            ErrorCode.NOT_AUTHORISED,
                            "Node ID is already bound to another identity key",
                        )
                    raise BarnError(ErrorCode.INVALID_REQUEST, "Node already has an enrolment")
            try:
                repository.add_enrolment_request(
                    request_id=str(request_id),
                    invite_id=invite["invite_id"],
                    node_id=str(submission.node_id),
                    node_name=submission.node_name,
                    identity_public_key=submission.identity_public_key,
                    csr_pem=submission.csr_pem,
                    advertised_host=submission.advertised_host,
                    peer_port=submission.peer_port,
                    protocol_version=submission.protocol_version,
                    receipt_digest=_secret_digest(receipt),
                    created_at=checked_at.isoformat(),
                    challenge_id=challenge["challenge_id"],
                )
            except sqlite3.IntegrityError as exc:
                raise BarnError(ErrorCode.INVALID_REQUEST, "Enrolment request conflicts") from exc
        return EnrolmentReceipt(
            request_id=request_id,
            receipt=receipt,
            status=EnrolmentStatus.AWAITING_APPROVAL,
        )

    def list_pending_enrolments(self) -> list[PendingEnrolment]:
        self.load_metadata()
        with CoordinatorRepository(self.database_path) as repository:
            rows = repository.list_pending_enrolments()
        return [
            PendingEnrolment(
                request_id=row["request_id"],
                node_id=row["node_id"],
                node_name=row["node_name"],
                advertised_host=row["advertised_host"],
                peer_port=row["peer_port"],
                identity_fingerprint=public_key_fingerprint(
                    load_public_key(row["identity_public_key"])
                ),
                created_at=_utc(row["created_at"]),
            )
            for row in rows
        ]

    def approve_enrolment(
        self,
        request_id: str,
        *,
        now: datetime | None = None,
    ) -> EnrolmentResult:
        metadata = self.load_metadata()
        decided_at = now or datetime.now(UTC)
        with CoordinatorRepository(self.database_path) as repository:
            request = repository.get_enrolment_request(request_id)
            if request is None:
                raise BarnError(ErrorCode.INVALID_REQUEST, "Enrolment request was not found")
            if request["status"] == EnrolmentStatus.APPROVED:
                return self._result_from_row(request, metadata)
            if request["status"] != EnrolmentStatus.AWAITING_APPROVAL:
                raise BarnError(ErrorCode.NOT_AUTHORISED, "Enrolment request is not pending")
            invite = repository.connection.execute(
                "SELECT * FROM enrolment_invites WHERE invite_id = ?",
                (request["invite_id"],),
            ).fetchone()
            if invite is None or _utc(invite["expires_at"]) <= decided_at:
                raise BarnError(ErrorCode.NOT_AUTHORISED, "Invitation expired before approval")

            csr = x509.load_pem_x509_csr(request["csr_pem"])
            ca_key = load_private_identity(self.state_dir / "secrets" / "ca-key.pem")
            ca_certificate = load_certificate(self.state_dir / "ca-cert.pem")
            grant_key = load_private_identity(self.state_dir / "secrets" / "grant-key.pem")
            certificate = issue_node_certificate(
                ca_key,
                ca_certificate,
                csr,
                str(metadata.barn_id),
                grant_key.public_key(),
            )
            certificate_pem = certificate.public_bytes(serialization.Encoding.PEM)
            ca_pem = ca_certificate.public_bytes(serialization.Encoding.PEM)
            grant_public_key = public_key_bytes(grant_key.public_key())
            try:
                repository.approve_enrolment(
                    request_id=request_id,
                    certificate_serial=str(certificate.serial_number),
                    certificate_pem=certificate_pem,
                    ca_certificate_pem=ca_pem,
                    grant_public_key=grant_public_key,
                    decided_at=decided_at.isoformat(),
                )
            except sqlite3.IntegrityError as exc:
                raise BarnError(ErrorCode.INVALID_REQUEST, "Approval conflicts with state") from exc
            approved = repository.get_enrolment_request(request_id)
            assert approved is not None
            return self._result_from_row(approved, metadata)

    def reject_enrolment(self, request_id: str, *, now: datetime | None = None) -> None:
        self.load_metadata()
        with CoordinatorRepository(self.database_path) as repository:
            if not repository.reject_enrolment(
                request_id, (now or datetime.now(UTC)).isoformat()
            ):
                raise BarnError(ErrorCode.INVALID_REQUEST, "Enrolment request is not pending")

    def poll_enrolment(self, receipt: str) -> EnrolmentResult:
        metadata = self.load_metadata()
        with CoordinatorRepository(self.database_path) as repository:
            request = repository.get_enrolment_by_receipt(_secret_digest(receipt))
        if request is None:
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Enrolment receipt is invalid")
        return self._result_from_row(request, metadata)

    def _authenticate_node(
        self, node_id: str, request: SignedRequest, *, now: datetime
    ) -> sqlite3.Row:
        with CoordinatorRepository(self.database_path) as repository:
            node = repository.get_node(node_id)
        if node is None or node["status"] == NodeStatus.REVOKED:
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Node is not an active Barn member")
        with NonceStore(self.state_dir / "auth-nonces.db") as nonce_store:
            verify_request(
                load_public_key(node["identity_public_key"]),
                request,
                node_id,
                nonce_store,
                now=now,
            )
        return node

    def accept_heartbeat(
        self,
        heartbeat: Heartbeat,
        request: SignedRequest,
        *,
        now: datetime | None = None,
    ) -> datetime:
        checked_at = now or datetime.now(UTC)
        if heartbeat.sent_at.tzinfo is None:
            raise BarnError(ErrorCode.INVALID_REQUEST, "Heartbeat time must include UTC offset")
        if heartbeat.storage_available > heartbeat.storage_total:
            raise BarnError(ErrorCode.INVALID_REQUEST, "Available storage exceeds total storage")
        self._authenticate_node(str(heartbeat.node_id), request, now=checked_at)
        host, separator, port_text = heartbeat.peer_endpoint.rpartition(":")
        if not separator or not host:
            raise BarnError(ErrorCode.INVALID_REQUEST, "Peer endpoint is invalid")
        try:
            port = int(port_text)
        except ValueError as exc:
            raise BarnError(ErrorCode.INVALID_REQUEST, "Peer endpoint is invalid") from exc
        if not 1 <= port <= 65535:
            raise BarnError(ErrorCode.INVALID_REQUEST, "Peer endpoint port is invalid")
        try:
            with CoordinatorRepository(self.database_path) as repository:
                accepted = repository.record_heartbeat(
                    node_id=str(heartbeat.node_id),
                    boot_epoch=str(heartbeat.boot_epoch),
                    sequence=heartbeat.sequence,
                    advertised_host=host,
                    peer_port=port,
                    software_version=heartbeat.software_version,
                    storage_total=heartbeat.storage_total,
                    storage_available=heartbeat.storage_available,
                    seen_at=checked_at.isoformat(),
                )
        except sqlite3.IntegrityError as exc:
            raise BarnError(
                ErrorCode.REPLAY_DETECTED, "Heartbeat sequence did not advance"
            ) from exc
        if not accepted:
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Node is not an active Barn member")
        return checked_at

    def list_registered_nodes(
        self,
        node_id: str,
        request: SignedRequest,
        *,
        now: datetime | None = None,
    ) -> list[RegisteredNode]:
        checked_at = now or datetime.now(UTC)
        self._authenticate_node(node_id, request, now=checked_at)
        with CoordinatorRepository(self.database_path) as repository:
            rows = repository.list_nodes()
        result = []
        for row in rows:
            last_seen = _utc(row["last_seen_at"]) if row["last_seen_at"] else None
            if row["status"] == NodeStatus.REVOKED:
                status = NodeStatus.REVOKED
            elif last_seen is None or checked_at - last_seen > timedelta(seconds=120):
                status = NodeStatus.OFFLINE
            elif checked_at - last_seen > timedelta(seconds=45):
                status = NodeStatus.SUSPECT
            else:
                status = NodeStatus.ONLINE
            result.append(
                RegisteredNode(
                    node_id=row["node_id"],
                    name=row["name"],
                    status=status,
                    peer_endpoint=f"{row['advertised_host']}:{row['peer_port']}",
                    software_version=row["software_version"],
                    storage_total=row["storage_total"],
                    storage_available=row["storage_available"],
                    last_seen_at=last_seen,
                )
            )
        return result

    def create_share(
        self,
        file_id: UUID,
        source_node_id: UUID,
        recipient_node_id: UUID,
        ttl: timedelta,
        *,
        now: datetime | None = None,
    ) -> FileShare:
        created_at = now or datetime.now(UTC)
        if ttl <= timedelta(0) or ttl > timedelta(days=30):
            raise BarnError(
                ErrorCode.INVALID_REQUEST, "Share TTL must be between 1 second and 30 days"
            )
        expires_at = created_at + ttl
        if source_node_id == recipient_node_id:
            raise BarnError(ErrorCode.INVALID_REQUEST, "Share recipient must be another node")
        with CoordinatorRepository(self.database_path) as repository:
            source = repository.get_node(str(source_node_id))
            recipient = repository.get_node(str(recipient_node_id))
            if source is None or source["status"] == NodeStatus.REVOKED:
                raise BarnError(
                    ErrorCode.NOT_AUTHORISED, "Source node is not an active Barn member"
                )
            if recipient is None or recipient["status"] == NodeStatus.REVOKED:
                raise BarnError(
                    ErrorCode.NOT_AUTHORISED, "Recipient node is not an active Barn member"
                )
            share = FileShare(
                share_id=uuid4(),
                file_id=file_id,
                source_node_id=source_node_id,
                recipient_node_id=recipient_node_id,
                created_at=created_at,
                expires_at=expires_at,
            )
            repository.add_share(
                share_id=str(share.share_id),
                file_id=str(file_id),
                source_node_id=str(source_node_id),
                recipient_node_id=str(recipient_node_id),
                created_at=created_at.isoformat(),
                expires_at=expires_at.isoformat(),
            )
        return share

    def list_shares(self, *, recipient_node_id: UUID | None = None) -> list[FileShare]:
        self.load_metadata()
        with CoordinatorRepository(self.database_path) as repository:
            rows = repository.list_shares(
                recipient_node_id=str(recipient_node_id) if recipient_node_id else None
            )
        return [
            FileShare(
                share_id=row["share_id"],
                file_id=row["file_id"],
                source_node_id=row["source_node_id"],
                recipient_node_id=row["recipient_node_id"],
                created_at=_utc(row["created_at"]),
                expires_at=_utc(row["expires_at"]),
                revoked_at=_utc(row["revoked_at"]) if row["revoked_at"] else None,
            )
            for row in rows
        ]

    def revoke_share(self, share_id: UUID, *, now: datetime | None = None) -> None:
        self.load_metadata()
        revoked_at = now or datetime.now(UTC)
        with CoordinatorRepository(self.database_path) as repository:
            if not repository.revoke_share(str(share_id), revoked_at.isoformat()):
                raise BarnError(
                    ErrorCode.INVALID_REQUEST, "Share is unavailable or already revoked"
                )

    def issue_transfer_grant(
        self,
        share_id: UUID,
        recipient_node_id: UUID,
        *,
        now: datetime | None = None,
    ) -> TransferGrant:
        issued_at = now or datetime.now(UTC)
        with CoordinatorRepository(self.database_path) as repository:
            row = repository.get_share(str(share_id))
            if row is None:
                raise BarnError(ErrorCode.NOT_AUTHORISED, "Share is unavailable")
            if row["recipient_node_id"] != str(recipient_node_id):
                raise BarnError(ErrorCode.NOT_AUTHORISED, "Share is addressed to another node")
            if row["revoked_at"] or issued_at >= _utc(row["expires_at"]):
                raise BarnError(ErrorCode.NOT_AUTHORISED, "Share is expired or revoked")
            recipient = repository.get_node(str(recipient_node_id))
            if recipient is None or recipient["status"] == NodeStatus.REVOKED:
                raise BarnError(
                    ErrorCode.NOT_AUTHORISED,
                    "Recipient node is not an active Barn member",
                )
        expires_at = min(_utc(row["expires_at"]), issued_at + timedelta(minutes=5))
        grant_id = uuid4()
        transfer_id = uuid4()
        signature = load_private_identity(self.state_dir / "secrets" / "grant-key.pem").sign(
            canonical_transfer_grant(
                grant_id,
                share_id,
                transfer_id,
                UUID(row["file_id"]),
                UUID(row["source_node_id"]),
                recipient_node_id,
                issued_at,
                expires_at,
            )
        )
        return TransferGrant(
            grant_id=grant_id,
            share_id=share_id,
            transfer_id=transfer_id,
            file_id=row["file_id"],
            source_node_id=row["source_node_id"],
            recipient_node_id=recipient_node_id,
            issued_at=issued_at,
            expires_at=expires_at,
            signature=signature,
        )

    def issue_relay_ticket(
        self,
        source_node_id: UUID,
        recipient_node_id: UUID,
        *,
        ttl: timedelta = timedelta(minutes=5),
        now: datetime | None = None,
    ) -> RelayTicket:
        issued_at = now or datetime.now(UTC)
        if ttl <= timedelta(0) or ttl > timedelta(minutes=5):
            raise BarnError(
                ErrorCode.INVALID_REQUEST,
                "Relay ticket TTL must be between 1 second and 5 minutes",
            )
        metadata = self.load_metadata()
        if source_node_id == recipient_node_id:
            raise BarnError(ErrorCode.INVALID_REQUEST, "Relay peers must be different nodes")
        with CoordinatorRepository(self.database_path) as repository:
            for node_id in (source_node_id, recipient_node_id):
                node = repository.get_node(str(node_id))
                if node is None or node["status"] == NodeStatus.REVOKED:
                    raise BarnError(
                        ErrorCode.NOT_AUTHORISED,
                        "Relay peer is not an active Barn member",
                    )
        expires_at = issued_at + ttl
        ticket_id = uuid4()
        signature = load_private_identity(self.state_dir / "secrets" / "grant-key.pem").sign(
            canonical_relay_ticket(
                ticket_id, metadata.barn_id, source_node_id, recipient_node_id,
                issued_at, expires_at,
            )
        )
        return RelayTicket(
            ticket_id=ticket_id,
            barn_id=metadata.barn_id,
            source_node_id=source_node_id,
            recipient_node_id=recipient_node_id,
            issued_at=issued_at,
            expires_at=expires_at,
            signature=signature,
        )

    @staticmethod
    def _result_from_row(
        request: sqlite3.Row, metadata: CoordinatorMetadata
    ) -> EnrolmentResult:
        status = EnrolmentStatus(request["status"])
        approved = status is EnrolmentStatus.APPROVED
        return EnrolmentResult(
            request_id=request["request_id"],
            status=status,
            barn_id=metadata.barn_id if approved else None,
            certificate_pem=request["certificate_pem"] if approved else None,
            ca_certificate_pem=request["ca_certificate_pem"] if approved else None,
            grant_public_key=request["grant_public_key"] if approved else None,
            decided_at=_utc(request["decided_at"]) if request["decided_at"] else None,
        )
