"""Coordinator initialization and invitation lifecycle."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from pydantic import BaseModel, ConfigDict

from ..config import ensure_private_directory, write_private_bytes, write_private_json
from ..crypto import (
    certificate_fingerprint,
    create_barn_ca,
    create_server_certificate,
    generate_identity,
    load_certificate,
    save_certificate,
    save_private_identity,
)
from ..errors import BarnError, ErrorCode
from .repository import CoordinatorRepository


class CoordinatorMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    barn_id: str
    name: str
    advertised_host: str
    created_at: datetime
    ca_fingerprint: str


@dataclass(frozen=True, slots=True)
class CreatedInvite:
    invite_id: str
    code: str
    expires_at: datetime


def _validate_name(name: str) -> str:
    clean = name.strip()
    if not clean or len(clean) > 100 or any(ord(character) < 32 for character in clean):
        raise BarnError(ErrorCode.INVALID_REQUEST, "Barn name must be 1-100 printable characters")
    return clean


def _invite_digest(code: str) -> bytes:
    return hashlib.sha256(code.encode("ascii")).digest()


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
