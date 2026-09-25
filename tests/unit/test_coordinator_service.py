import sqlite3
from datetime import timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import ExtensionOID

from barn_compute.coordinator.repository import CoordinatorRepository
from barn_compute.coordinator.service import CoordinatorService, _invite_digest
from barn_compute.errors import BarnError, ErrorCode


def test_initialize_creates_durable_barn_state(tmp_path) -> None:
    state_dir = tmp_path / "coordinator"
    service = CoordinatorService(state_dir)
    metadata = service.initialize("LabBarn", "127.0.0.1")

    assert metadata.name == "LabBarn"
    assert metadata.advertised_host == "127.0.0.1"
    assert len(metadata.ca_fingerprint) == 64
    assert (state_dir / "coordinator.db").is_file()
    assert (state_dir / "secrets" / "ca-key.pem").is_file()
    assert (state_dir / "secrets" / "grant-key.pem").is_file()
    assert (state_dir / "secrets" / "admin.token").is_file()

    certificate = x509.load_pem_x509_certificate(
        (state_dir / "coordinator-cert.pem").read_bytes()
    )
    san = certificate.extensions.get_extension_for_oid(
        ExtensionOID.SUBJECT_ALTERNATIVE_NAME
    ).value
    assert san.get_values_for_type(x509.IPAddress)[0].compressed == "127.0.0.1"

    with pytest.raises(BarnError) as duplicate:
        service.initialize("Another", "127.0.0.1")
    assert duplicate.value.code == ErrorCode.CONFIGURATION


def test_ca_export_contains_public_certificate_only(tmp_path) -> None:
    service = CoordinatorService(tmp_path / "coordinator")
    metadata = service.initialize("LabBarn", "localhost")
    output = tmp_path / "exports" / "barn-ca.pem"
    fingerprint = service.export_ca(output)

    assert fingerprint == metadata.ca_fingerprint
    assert b"BEGIN CERTIFICATE" in output.read_bytes()
    assert b"PRIVATE KEY" not in output.read_bytes()


def test_invite_persists_only_digest(tmp_path) -> None:
    service = CoordinatorService(tmp_path / "coordinator")
    service.initialize("LabBarn", "localhost")
    invite = service.create_invite(timedelta(minutes=10))

    database_bytes = service.database_path.read_bytes()
    assert invite.code.encode("ascii") not in database_bytes
    with CoordinatorRepository(service.database_path) as repository:
        row = repository.get_invite_by_digest(_invite_digest(invite.code))
    assert row is not None
    assert row["invite_id"] == invite.invite_id
    assert row["consumed_at"] is None


@pytest.mark.parametrize("ttl", [timedelta(seconds=59), timedelta(hours=25)])
def test_invite_ttl_is_bounded(tmp_path, ttl) -> None:
    service = CoordinatorService(tmp_path / "coordinator")
    service.initialize("LabBarn", "localhost")
    with pytest.raises(BarnError) as error:
        service.create_invite(ttl)
    assert error.value.code == ErrorCode.INVALID_REQUEST


def test_private_keys_are_ed25519_pem(tmp_path) -> None:
    service = CoordinatorService(tmp_path / "coordinator")
    service.initialize("LabBarn", "localhost")
    key_data = (service.state_dir / "secrets" / "grant-key.pem").read_bytes()
    key = serialization.load_pem_private_key(key_data, password=None)
    assert isinstance(key, Ed25519PrivateKey)


def test_schema_migrates_existing_enrolment_table(tmp_path) -> None:
    database = tmp_path / "coordinator.db"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE enrolment_requests (
            request_id TEXT PRIMARY KEY,
            invite_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            node_name TEXT NOT NULL,
            identity_public_key BLOB NOT NULL,
            csr_pem BLOB NOT NULL,
            advertised_host TEXT NOT NULL,
            peer_port INTEGER NOT NULL,
            protocol_version TEXT NOT NULL,
            status TEXT NOT NULL,
            receipt_digest BLOB NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            decided_at TEXT
        );
        """
    )
    connection.close()

    with CoordinatorRepository(database) as repository:
        repository.migrate()
        columns = {
            row["name"]
            for row in repository.connection.execute(
                "PRAGMA table_info(enrolment_requests)"
            )
        }
        challenge_table = repository.connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'enrolment_challenges'
            """
        ).fetchone()
    assert {"certificate_pem", "ca_certificate_pem", "grant_public_key"} <= columns
    assert challenge_table is not None
