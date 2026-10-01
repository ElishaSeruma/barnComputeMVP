"""Durable node identity and enrolment proof handling."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import stat
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
    load_public_key,
    public_key_bytes,
    public_key_fingerprint,
    save_private_identity,
)
from ..errors import BarnError, ErrorCode
from ..grants import canonical_transfer_grant
from ..models import (
    CHUNK_SIZE,
    MAX_FILE_SIZE,
    PROTOCOL_VERSION,
    ChunkManifest,
    ControlGrant,
    EnrolmentChallenge,
    EnrolmentResult,
    EnrolmentStatus,
    EnrolmentSubmission,
    FileManifest,
    Heartbeat,
    NodeStatus,
    TransferGrant,
    TransferJournal,
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

    def confined(self, *parts: str) -> Path:
        path = self.state_dir
        for part in parts:
            if part in (".", "..") or "/" in part or "\\" in part:
                raise BarnError(ErrorCode.INVALID_REQUEST, "Unsafe managed path")
            path = path / part
            try:
                info = path.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise BarnError(
                    ErrorCode.CONFIGURATION, "Managed path contains a link or reparse point"
                )
        return path

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
                (self.state_dir / "secrets" / "enrolment-receipt.token")
                .read_text(encoding="ascii")
                .strip()
            )
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
        pinned_ca = x509.load_pem_x509_certificate((self.state_dir / "trusted-ca.pem").read_bytes())
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
        if result.control_grant is not None:
            from ..api_models import encode_binary

            payload = result.control_grant.model_dump(mode="json", exclude={"signature"})
            payload["signature"] = encode_binary(result.control_grant.signature)
            self.store_control_grant(payload)
        (self.state_dir / "secrets" / "enrolment-receipt.token").unlink(missing_ok=True)
        return approved

    def store_control_grant(self, payload: dict[str, object]) -> ControlGrant:
        from ..api_models import decode_binary, encode_binary
        from ..grants import canonical_control_grant

        value = dict(payload)
        value["signature"] = decode_binary(str(value["signature"]))
        grant = ControlGrant.model_validate(value)
        metadata = self.load_metadata()
        if grant.barn_id != metadata.barn_id or grant.node_id != metadata.node_id:
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Control grant scope is invalid")
        identity = public_key_bytes(
            load_private_identity(self.state_dir / "secrets" / "identity-key.pem").public_key()
        )
        if decode_binary(grant.node_identity_key) != identity:
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Control grant identity is invalid")
        load_public_key((self.state_dir / "grant-public.key").read_bytes()).verify(
            grant.signature,
            canonical_control_grant(
                grant.grant_id,
                grant.barn_id,
                grant.node_id,
                grant.node_identity_key,
                grant.issued_at,
                grant.expires_at,
            ),
        )
        stored = grant.model_dump(mode="json", exclude={"signature"})
        stored["signature"] = encode_binary(grant.signature)
        write_private_json(self.state_dir / "control-grant.json", stored)
        return grant

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

    def import_file(self, source: Path, *, display_name: str | None = None) -> FileManifest:
        source = source.expanduser()
        if source.is_symlink() or not source.is_file():
            raise BarnError(ErrorCode.INVALID_REQUEST, "Source must be a regular file")
        try:
            source = source.resolve(strict=True)
            size = source.stat().st_size
        except OSError as exc:
            raise BarnError(ErrorCode.INVALID_REQUEST, "Source file is unavailable") from exc
        if size > MAX_FILE_SIZE:
            raise BarnError(ErrorCode.INVALID_REQUEST, "File exceeds the 512 MiB maximum")

        metadata = self.load_metadata()
        managed_dir = ensure_private_directory(self.confined("managed"))
        if shutil.disk_usage(managed_dir).free < size + CHUNK_SIZE:
            raise BarnError(ErrorCode.CONFIGURATION, "Insufficient managed storage")
        file_id = uuid4()
        file_dir = managed_dir / str(file_id)
        staging_path = managed_dir / f".{file_id}.staging"
        chunks: list[ChunkManifest] = []
        file_hash = hashlib.sha256()
        copied = 0
        completed = False
        try:
            with source.open("rb") as source_handle, staging_path.open("xb") as staged:
                while True:
                    chunk = source_handle.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    digest = hashlib.sha256(chunk).hexdigest()
                    chunks.append(
                        ChunkManifest(
                            index=len(chunks),
                            offset=copied,
                            length=len(chunk),
                            sha256=digest,
                        )
                    )
                    staged.write(chunk)
                    file_hash.update(chunk)
                    copied += len(chunk)
                    if copied > MAX_FILE_SIZE:
                        raise BarnError(ErrorCode.INVALID_REQUEST, "File grew beyond maximum size")
                staged.flush()
                os.fsync(staged.fileno())
            if copied != size:
                raise BarnError(ErrorCode.INVALID_REQUEST, "Source changed during import")
            if shutil.disk_usage(managed_dir).free < copied:
                raise BarnError(ErrorCode.CONFIGURATION, "Insufficient managed storage")
            file_dir.mkdir(mode=0o700)
            os.replace(staging_path, file_dir / "data")
            manifest = FileManifest(
                file_id=file_id,
                owner_node_id=metadata.node_id,
                display_name=display_name or source.name,
                size=copied,
                sha256=file_hash.hexdigest(),
                chunks=tuple(chunks),
                created_at=datetime.now(UTC),
            )
            write_private_json(file_dir / "manifest.json", manifest.model_dump(mode="json"))
            completed = True
            return manifest
        except BarnError:
            raise
        except (OSError, ValueError) as exc:
            raise BarnError(ErrorCode.CONFIGURATION, "Managed file import failed") from exc
        finally:
            staging_path.unlink(missing_ok=True)
            if not completed and file_dir.exists():
                shutil.rmtree(file_dir)

    def list_files(self) -> list[FileManifest]:
        managed_dir = self.confined("managed")
        if not managed_dir.exists():
            return []
        manifests: list[FileManifest] = []
        for manifest_path in sorted(managed_dir.glob("*/manifest.json")):
            self.confined("managed", manifest_path.parent.name, "manifest.json")
            try:
                manifests.append(
                    FileManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
                )
            except (OSError, ValueError) as exc:
                raise BarnError(
                    ErrorCode.CONFIGURATION, "Managed file manifest is invalid"
                ) from exc
        return manifests

    def read_grant_chunk(
        self, grant: TransferGrant, index: int, *, now: datetime | None = None
    ) -> bytes:
        checked_at = now or datetime.now(UTC)
        if index < 0:
            raise BarnError(ErrorCode.INVALID_REQUEST, "Chunk index is invalid")
        metadata = self.load_metadata()
        if grant.source_node_id != metadata.node_id:
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Grant source does not match this node")
        if checked_at < grant.issued_at or checked_at >= grant.expires_at:
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Transfer grant is expired")
        try:
            load_public_key((self.state_dir / "grant-public.key").read_bytes()).verify(
                grant.signature,
                canonical_transfer_grant(
                    grant.grant_id,
                    grant.share_id,
                    grant.transfer_id,
                    grant.file_id,
                    grant.source_node_id,
                    grant.recipient_node_id,
                    grant.issued_at,
                    grant.expires_at,
                ),
            )
        except (InvalidSignature, OSError, ValueError) as exc:
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Transfer grant is invalid") from exc
        manifest_path = self.confined("managed", str(grant.file_id), "manifest.json")
        data_path = self.confined("managed", str(grant.file_id), "data")
        try:
            manifest = FileManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
            chunk = manifest.chunks[index]
        except (IndexError, OSError, ValueError) as exc:
            raise BarnError(
                ErrorCode.INVALID_REQUEST, "Requested file chunk is unavailable"
            ) from exc
        if manifest.file_id != grant.file_id or manifest.owner_node_id != metadata.node_id:
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Grant file scope is invalid")
        try:
            with data_path.open("rb") as handle:
                handle.seek(chunk.offset)
                payload = handle.read(chunk.length)
        except OSError as exc:
            raise BarnError(ErrorCode.CONFIGURATION, "Managed file is unavailable") from exc
        if len(payload) != chunk.length or hashlib.sha256(payload).hexdigest() != chunk.sha256:
            raise BarnError(ErrorCode.CONFIGURATION, "Managed file chunk failed integrity check")
        return payload

    def start_transfer(
        self, grant: TransferGrant, manifest: FileManifest, *, revalidate: bool = True
    ) -> TransferJournal:
        metadata = self.load_metadata()
        if grant.recipient_node_id != metadata.node_id:
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Grant recipient does not match this node")
        if grant.file_id != manifest.file_id:
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Grant file scope is invalid")
        if manifest.owner_node_id != grant.source_node_id:
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Manifest owner does not match source")
        self._verify_transfer_grant(grant)
        transfer_dir = ensure_private_directory(self.confined("transfers", str(grant.transfer_id)))
        journal_path = self.confined("transfers", str(grant.transfer_id), "journal.json")
        if journal_path.exists():
            try:
                journal = TransferJournal.model_validate_json(
                    journal_path.read_text(encoding="utf-8")
                )
            except (OSError, ValueError) as exc:
                raise BarnError(ErrorCode.CONFIGURATION, "Transfer journal is invalid") from exc
            if journal.file_id != manifest.file_id or journal.manifest_sha256 != manifest.sha256:
                raise BarnError(ErrorCode.INVALID_REQUEST, "Transfer manifest changed")
            if journal.cancelled:
                raise BarnError(ErrorCode.CONFIGURATION, "Transfer is cancelled; resume it first")
            if not revalidate:
                return journal
            valid = []
            for index in journal.completed_chunks:
                if index < 0 or index >= len(manifest.chunks):
                    raise BarnError(ErrorCode.CONFIGURATION, "Transfer journal index is invalid")
                chunk_path = transfer_dir / f"chunk-{index:08d}.bin"
                if chunk_path.is_symlink():
                    raise BarnError(ErrorCode.CONFIGURATION, "Transfer chunk path is unsafe")
                try:
                    data = chunk_path.read_bytes()
                except FileNotFoundError:
                    continue
                chunk = manifest.chunks[index]
                if len(data) == chunk.length and hashlib.sha256(data).hexdigest() == chunk.sha256:
                    valid.append(index)
            if tuple(valid) != journal.completed_chunks:
                journal = journal.model_copy(update={"completed_chunks": tuple(valid)})
                write_private_json(journal_path, journal.model_dump(mode="json"))
            return journal
        if shutil.disk_usage(transfer_dir).free < manifest.size * 4 + CHUNK_SIZE:
            raise BarnError(ErrorCode.CONFIGURATION, "Insufficient transfer storage")
        journal = TransferJournal(
            transfer_id=grant.transfer_id,
            file_id=manifest.file_id,
            manifest_sha256=manifest.sha256,
        )
        write_private_json(journal_path, journal.model_dump(mode="json"))
        return journal

    def accept_transfer_chunk(
        self,
        grant: TransferGrant,
        manifest: FileManifest,
        index: int,
        payload: bytes,
    ) -> TransferJournal:
        journal = self.start_transfer(grant, manifest, revalidate=False)
        if index < 0 or index >= len(manifest.chunks):
            raise BarnError(ErrorCode.INVALID_REQUEST, "Transfer chunk index is invalid")
        chunk = manifest.chunks[index]
        if len(payload) != chunk.length or hashlib.sha256(payload).hexdigest() != chunk.sha256:
            raise BarnError(ErrorCode.INVALID_REQUEST, "Transfer chunk failed integrity check")
        if index in journal.completed_chunks:
            return journal
        transfer_dir = self.confined("transfers", str(grant.transfer_id))
        write_private_bytes(
            self.confined("transfers", str(grant.transfer_id), f"chunk-{index:08d}.bin"), payload
        )
        updated = journal.model_copy(
            update={"completed_chunks": tuple(sorted((*journal.completed_chunks, index)))}
        )
        write_private_json(transfer_dir / "journal.json", updated.model_dump(mode="json"))
        return updated

    def assemble_transfer(self, grant: TransferGrant, manifest: FileManifest) -> Path:
        journal = self.start_transfer(grant, manifest, revalidate=False)
        expected = tuple(range(len(manifest.chunks)))
        if journal.completed_chunks != expected:
            raise BarnError(ErrorCode.INVALID_REQUEST, "Transfer is incomplete")
        assembled = self.confined("transfers", str(grant.transfer_id), "assembled.tmp")
        digest = hashlib.sha256()
        size = 0
        try:
            with assembled.open("wb") as output:
                for index in expected:
                    payload = self.confined(
                        "transfers", str(grant.transfer_id), f"chunk-{index:08d}.bin"
                    ).read_bytes()
                    output.write(payload)
                    digest.update(payload)
                    size += len(payload)
                output.flush()
                os.fsync(output.fileno())
        except OSError as exc:
            raise BarnError(ErrorCode.CONFIGURATION, "Transfer assembly failed") from exc
        if size != manifest.size or digest.hexdigest() != manifest.sha256:
            assembled.unlink(missing_ok=True)
            raise BarnError(ErrorCode.INVALID_REQUEST, "Assembled file failed integrity check")
        return assembled

    def export_transfer(
        self, grant: TransferGrant, manifest: FileManifest, destination: Path
    ) -> Path:
        destination = destination.expanduser().absolute()
        if destination.exists() or destination.is_symlink():
            raise BarnError(ErrorCode.CONFIGURATION, "Destination already exists")
        assembled = self.assemble_transfer(grant, manifest)
        try:
            journal = self.start_transfer(grant, manifest, revalidate=False)
            journal_path = self.confined("transfers", str(grant.transfer_id), "journal.json")
            if journal.managed_file_id is None:
                received = self.import_file(assembled, display_name=manifest.display_name)
                journal = journal.model_copy(update={"managed_file_id": received.file_id})
                write_private_json(journal_path, journal.model_dump(mode="json"))
            temporary = destination.with_name(f".{destination.name}.{grant.transfer_id}.tmp")
            try:
                ensure_private_directory(destination.parent)
                with assembled.open("rb") as source, temporary.open("xb") as output:
                    shutil.copyfileobj(source, output, CHUNK_SIZE)
                    output.flush()
                    os.fsync(output.fileno())
                # Atomic no-clobber publication, including a concurrent destination creation.
                os.link(temporary, destination)
                temporary.unlink()
            except OSError as exc:
                temporary.unlink(missing_ok=True)
                raise BarnError(ErrorCode.CONFIGURATION, "Transfer export failed") from exc
            journal = journal.model_copy(update={"exported": True})
            write_private_json(journal_path, journal.model_dump(mode="json"))
            return destination
        finally:
            assembled.unlink(missing_ok=True)

    def grant_manifest(self, grant: TransferGrant) -> FileManifest:
        self._verify_transfer_grant(grant)
        metadata = self.load_metadata()
        if grant.source_node_id != metadata.node_id:
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Grant source does not match node")
        path = self.confined("managed", str(grant.file_id), "manifest.json")
        try:
            manifest = FileManifest.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise BarnError(ErrorCode.INVALID_REQUEST, "Managed manifest is unavailable") from exc
        if manifest.file_id != grant.file_id or manifest.owner_node_id != metadata.node_id:
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Manifest scope is invalid")
        return manifest

    def transfer_control(self, transfer_id: UUID, *, cancelled: bool) -> TransferJournal:
        path = self.confined("transfers", str(transfer_id), "journal.json")
        try:
            journal = TransferJournal.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise BarnError(ErrorCode.INVALID_REQUEST, "Transfer is unavailable") from exc
        journal = journal.model_copy(update={"cancelled": cancelled})
        write_private_json(path, journal.model_dump(mode="json"))
        return journal

    def _verify_transfer_grant(self, grant: TransferGrant) -> None:
        checked_at = datetime.now(UTC)
        if checked_at < grant.issued_at or checked_at >= grant.expires_at:
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Transfer grant is expired")
        try:
            load_public_key((self.state_dir / "grant-public.key").read_bytes()).verify(
                grant.signature,
                canonical_transfer_grant(
                    grant.grant_id,
                    grant.share_id,
                    grant.transfer_id,
                    grant.file_id,
                    grant.source_node_id,
                    grant.recipient_node_id,
                    grant.issued_at,
                    grant.expires_at,
                ),
            )
        except (InvalidSignature, OSError, ValueError) as exc:
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Transfer grant is invalid") from exc
