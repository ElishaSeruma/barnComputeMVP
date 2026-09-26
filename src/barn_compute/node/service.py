"""Durable node identity and enrolment proof handling."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from pydantic import BaseModel, ConfigDict

from .. import __version__
from ..config import ensure_private_directory, write_private_bytes, write_private_json
from ..crypto import (
    BARN_ID_OID,
    GRANT_PUBLIC_KEY_OID,
    certificate_fingerprint,
    certificate_san_matches,
    create_node_csr,
    generate_identity,
    load_private_identity,
    public_key_bytes,
    public_key_fingerprint,
    save_private_identity,
)
from ..errors import BarnError, ErrorCode
from ..models import (
    PROTOCOL_VERSION,
    EnrolmentChallenge,
    EnrolmentResult,
    EnrolmentStatus,
    EnrolmentSubmission,
    Heartbeat,
    NodeStatus,
)

ENROLMENT_PROOF_DOMAIN = b"barn-enrolment-proof-v1\n"


class NodeMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: UUID
    name: str
    advertised_host: str
    peer_port: int
    created_at: datetime
    identity_fingerprint: str
    status: NodeStatus = NodeStatus.UNREGISTERED
    barn_id: UUID | None = None
    enrolment_request_id: UUID | None = None


class HeartbeatState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    boot_epoch: UUID
    sequence: int


def _valid_name(name: str) -> str:
    clean = name.strip()
    if not clean or len(clean) > 100 or any(ord(character) < 32 for character in clean):
        raise BarnError(ErrorCode.INVALID_REQUEST, "Node name must be 1-100 printable characters")
    return clean


def _valid_host(host: str) -> str:
    clean = host.strip()
    if not clean or len(clean) > 253 or any(character.isspace() for character in clean):
        raise BarnError(ErrorCode.INVALID_REQUEST, "Advertised host is invalid")
    return clean


def canonical_enrolment_proof(
    challenge: str,
    node_id: UUID,
    csr_pem: bytes,
    advertised_host: str,
    peer_port: int,
    protocol_version: str,
) -> bytes:
    fields = (
        challenge,
        str(node_id),
        hashlib.sha256(csr_pem).hexdigest(),
        advertised_host,
        str(peer_port),
        protocol_version,
    )
    if any("\n" in field or "\r" in field for field in fields):
        raise BarnError(ErrorCode.INVALID_REQUEST, "Enrolment proof fields contain newlines")
    return ENROLMENT_PROOF_DOMAIN + "\n".join(fields).encode("utf-8")


class NodeService:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir.expanduser().resolve()

    @property
    def metadata_path(self) -> Path:
        return self.state_dir / "node.json"

    def initialize(
        self,
        name: str,
        advertised_host: str,
        peer_port: int = 8445,
    ) -> NodeMetadata:
        name = _valid_name(name)
        advertised_host = _valid_host(advertised_host)
        if not 1 <= peer_port <= 65535:
            raise BarnError(ErrorCode.INVALID_REQUEST, "Peer port must be between 1 and 65535")
        if self.state_dir.exists():
            raise BarnError(
                ErrorCode.CONFIGURATION, f"Node state already exists at {self.state_dir}"
            )

        ensure_private_directory(self.state_dir.parent)
        staging = self.state_dir.parent / f".{self.state_dir.name}.init-{uuid4().hex}"
        ensure_private_directory(staging)
        try:
            node_id = uuid4()
            identity_key = generate_identity()
            tls_key = generate_identity()
            csr = create_node_csr(
                tls_key,
                str(node_id),
                name,
                advertised_host,
            )
            save_private_identity(identity_key, staging / "secrets" / "identity-key.pem")
            save_private_identity(tls_key, staging / "secrets" / "tls-key.pem")
            write_private_bytes(
                staging / "node.csr.pem",
                csr.public_bytes(serialization.Encoding.PEM),
            )
            write_private_bytes(
                staging / "secrets" / "admin.token",
                (secrets.token_urlsafe(32) + "\n").encode("ascii"),
            )
            metadata = NodeMetadata(
                node_id=node_id,
                name=name,
                advertised_host=advertised_host,
                peer_port=peer_port,
                created_at=datetime.now(UTC),
                identity_fingerprint=public_key_fingerprint(identity_key.public_key()),
            )
            write_private_json(staging / "node.json", metadata.model_dump(mode="json"))
            os.replace(staging, self.state_dir)
            return metadata
        except Exception:
            if staging.exists():
                shutil.rmtree(staging)
            raise

    def load_metadata(self) -> NodeMetadata:
        if not self.metadata_path.exists():
            raise BarnError(ErrorCode.CONFIGURATION, f"Node is not initialized at {self.state_dir}")
        try:
            return NodeMetadata.model_validate_json(self.metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise BarnError(ErrorCode.CONFIGURATION, "Node metadata is invalid") from exc

    def create_submission(self, challenge: EnrolmentChallenge) -> EnrolmentSubmission:
        metadata = self.load_metadata()
        if metadata.status not in (NodeStatus.UNREGISTERED, NodeStatus.PENDING):
            raise BarnError(ErrorCode.INVALID_REQUEST, "Node is already enrolled")
        if challenge.expires_at <= datetime.now(UTC):
            raise BarnError(ErrorCode.INVALID_REQUEST, "Enrolment challenge has expired")
        if not (self.state_dir / "trusted-ca.pem").exists():
            raise BarnError(ErrorCode.CONFIGURATION, "A verified Barn CA must be pinned first")
        identity_key = load_private_identity(self.state_dir / "secrets" / "identity-key.pem")
        csr_pem = (self.state_dir / "node.csr.pem").read_bytes()
        proof_message = canonical_enrolment_proof(
            challenge.challenge,
            metadata.node_id,
            csr_pem,
            metadata.advertised_host,
            metadata.peer_port,
            PROTOCOL_VERSION,
        )
        return EnrolmentSubmission(
            node_id=metadata.node_id,
            node_name=metadata.name,
            advertised_host=metadata.advertised_host,
            peer_port=metadata.peer_port,
            identity_public_key=public_key_bytes(identity_key.public_key()),
            csr_pem=csr_pem,
            challenge=challenge.challenge,
            proof=identity_key.sign(proof_message),
        )

    def pin_barn_ca(self, certificate_pem: bytes, expected_fingerprint: str) -> str:
        certificate = x509.load_pem_x509_certificate(certificate_pem)
        fingerprint = certificate_fingerprint(certificate)
        if fingerprint.lower() != expected_fingerprint.lower():
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Barn CA fingerprint does not match")
        try:
            constraints = certificate.extensions.get_extension_for_class(
                x509.BasicConstraints
            ).value
            if not constraints.ca or certificate.issuer != certificate.subject:
                raise ValueError("certificate is not a self-signed CA")
            certificate.public_key().verify(
                certificate.signature, certificate.tbs_certificate_bytes
            )
        except (InvalidSignature, ValueError, x509.ExtensionNotFound) as exc:
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Barn CA is invalid") from exc
        write_private_bytes(self.state_dir / "trusted-ca.pem", certificate_pem)
        return fingerprint

    def record_receipt(self, request_id: UUID, receipt: str) -> NodeMetadata:
        write_private_bytes(
            self.state_dir / "secrets" / "enrolment-receipt.token",
            (receipt + "\n").encode("ascii"),
        )
        metadata = self.load_metadata().model_copy(
            update={
                "status": NodeStatus.PENDING,
                "enrolment_request_id": request_id,
            }
        )
        write_private_json(self.metadata_path, metadata.model_dump(mode="json"))
        return metadata

    def load_receipt(self) -> str:
        try:
            return (
                self.state_dir / "secrets" / "enrolment-receipt.token"
            ).read_text(encoding="ascii").strip()
        except OSError as exc:
            raise BarnError(ErrorCode.CONFIGURATION, "Enrolment receipt is unavailable") from exc

    def complete_enrolment(self, result: EnrolmentResult) -> NodeMetadata:
        if result.status is not EnrolmentStatus.APPROVED:
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Enrolment has not been approved")
        if not all(
            (
                result.barn_id,
                result.certificate_pem,
                result.ca_certificate_pem,
                result.grant_public_key,
            )
        ):
            raise BarnError(ErrorCode.INVALID_REQUEST, "Approved enrolment result is incomplete")

        metadata = self.load_metadata()
        certificate = x509.load_pem_x509_certificate(result.certificate_pem)
        ca_certificate = x509.load_pem_x509_certificate(result.ca_certificate_pem)
        pinned_ca = x509.load_pem_x509_certificate(
            (self.state_dir / "trusted-ca.pem").read_bytes()
        )
        if certificate_fingerprint(ca_certificate) != certificate_fingerprint(pinned_ca):
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Enrolment used an untrusted Barn CA")
        ca_public_key = ca_certificate.public_key()
        ca_public_key.verify(certificate.signature, certificate.tbs_certificate_bytes)

        tls_key = load_private_identity(self.state_dir / "secrets" / "tls-key.pem")
        certificate_public_key = certificate.public_key()
        if public_key_bytes(certificate_public_key) != public_key_bytes(tls_key.public_key()):
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Node certificate uses the wrong key")
        if not certificate_san_matches(certificate, metadata.advertised_host):
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Node certificate SAN is incorrect")

        barn_extension = certificate.extensions.get_extension_for_oid(BARN_ID_OID).value
        grant_extension = certificate.extensions.get_extension_for_oid(GRANT_PUBLIC_KEY_OID).value
        if barn_extension.value.decode() != str(result.barn_id):
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Node certificate has the wrong Barn ID")
        if grant_extension.value != result.grant_public_key:
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Grant key binding is invalid")

        write_private_bytes(self.state_dir / "node-cert.pem", result.certificate_pem)
        write_private_bytes(self.state_dir / "barn-ca.pem", result.ca_certificate_pem)
        write_private_bytes(self.state_dir / "grant-public.key", result.grant_public_key)
        approved = metadata.model_copy(
            update={"status": NodeStatus.APPROVED, "barn_id": result.barn_id}
        )
        write_private_json(self.metadata_path, approved.model_dump(mode="json"))
        (self.state_dir / "secrets" / "enrolment-receipt.token").unlink(missing_ok=True)
        return approved

    def next_heartbeat(self) -> Heartbeat:
        metadata = self.load_metadata()
        if metadata.status not in (
            NodeStatus.APPROVED,
            NodeStatus.ONLINE,
            NodeStatus.SUSPECT,
            NodeStatus.OFFLINE,
        ):
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Node is not approved")
        state_path = self.state_dir / "heartbeat.json"
        try:
            state = HeartbeatState.model_validate_json(state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            state = HeartbeatState(boot_epoch=uuid4(), sequence=0)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise BarnError(ErrorCode.CONFIGURATION, "Heartbeat state is invalid") from exc
        state = state.model_copy(update={"sequence": state.sequence + 1})
        write_private_json(state_path, state.model_dump(mode="json"))
        usage = shutil.disk_usage(self.state_dir)
        return Heartbeat(
            node_id=metadata.node_id,
            boot_epoch=state.boot_epoch,
            sequence=state.sequence,
            peer_endpoint=f"{metadata.advertised_host}:{metadata.peer_port}",
            software_version=__version__,
            storage_total=usage.total,
            storage_available=usage.free,
            sent_at=datetime.now(UTC),
        )

    def store_registry(self, payload: dict[str, object]) -> None:
        write_private_json(self.state_dir / "registry.json", payload)
