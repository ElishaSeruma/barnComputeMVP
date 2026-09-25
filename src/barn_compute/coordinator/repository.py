"""SQLite persistence for coordinator-owned state."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = 2


class CoordinatorRepository:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA journal_mode=WAL")

    def migrate(self) -> None:
        with self.connection:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS barns (
                    barn_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    advertised_host TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS nodes (
                    node_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    identity_public_key BLOB NOT NULL,
                    advertised_host TEXT NOT NULL,
                    peer_port INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    certificate_serial TEXT,
                    created_at TEXT NOT NULL,
                    approved_at TEXT,
                    revoked_at TEXT
                );
                CREATE TABLE IF NOT EXISTS enrolment_invites (
                    invite_id TEXT PRIMARY KEY,
                    code_digest BLOB NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_invites_expiry
                    ON enrolment_invites(expires_at);
                CREATE TABLE IF NOT EXISTS enrolment_requests (
                    request_id TEXT PRIMARY KEY,
                    invite_id TEXT NOT NULL REFERENCES enrolment_invites(invite_id),
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
                    decided_at TEXT,
                    certificate_pem BLOB,
                    ca_certificate_pem BLOB,
                    grant_public_key BLOB
                );
                CREATE INDEX IF NOT EXISTS idx_enrolment_status
                    ON enrolment_requests(status, created_at);
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    occurred_at TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    subject_id TEXT,
                    outcome TEXT NOT NULL,
                    detail TEXT
                );
                CREATE TABLE IF NOT EXISTS enrolment_challenges (
                    challenge_id TEXT PRIMARY KEY,
                    invite_id TEXT NOT NULL REFERENCES enrolment_invites(invite_id),
                    node_id TEXT NOT NULL,
                    challenge_digest BLOB NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_challenges_expiry
                    ON enrolment_challenges(expires_at);
                """
            )
            columns = {
                row["name"]
                for row in self.connection.execute("PRAGMA table_info(enrolment_requests)")
            }
            for name, definition in (
                ("certificate_pem", "BLOB"),
                ("ca_certificate_pem", "BLOB"),
                ("grant_public_key", "BLOB"),
            ):
                if name not in columns:
                    self.connection.execute(
                        f"ALTER TABLE enrolment_requests ADD COLUMN {name} {definition}"
                    )
            self.connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, datetime.now(UTC).isoformat()),
            )

    def add_barn(self, barn_id: str, name: str, advertised_host: str, created_at: str) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO barns(barn_id, name, advertised_host, created_at) VALUES (?, ?, ?, ?)",
                (barn_id, name, advertised_host, created_at),
            )

    def add_invite(
        self,
        invite_id: str,
        code_digest: bytes,
        created_at: str,
        expires_at: str,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO enrolment_invites(
                    invite_id, code_digest, created_at, expires_at
                ) VALUES (?, ?, ?, ?)
                """,
                (invite_id, code_digest, created_at, expires_at),
            )

    def get_invite_by_digest(self, code_digest: bytes) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM enrolment_invites WHERE code_digest = ?", (code_digest,)
        ).fetchone()

    def add_challenge(
        self,
        challenge_id: str,
        invite_id: str,
        node_id: str,
        challenge_digest: bytes,
        created_at: str,
        expires_at: str,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO enrolment_challenges(
                    challenge_id, invite_id, node_id, challenge_digest,
                    created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    challenge_id,
                    invite_id,
                    node_id,
                    challenge_digest,
                    created_at,
                    expires_at,
                ),
            )

    def get_challenge_by_digest(self, digest: bytes) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM enrolment_challenges WHERE challenge_digest = ?", (digest,)
        ).fetchone()

    def invite_has_active_request(self, invite_id: str) -> bool:
        row = self.connection.execute(
            """
            SELECT 1 FROM enrolment_requests
            WHERE invite_id = ? AND status IN ('AWAITING_APPROVAL', 'APPROVED')
            LIMIT 1
            """,
            (invite_id,),
        ).fetchone()
        return row is not None

    def add_enrolment_request(
        self,
        *,
        request_id: str,
        invite_id: str,
        node_id: str,
        node_name: str,
        identity_public_key: bytes,
        csr_pem: bytes,
        advertised_host: str,
        peer_port: int,
        protocol_version: str,
        receipt_digest: bytes,
        created_at: str,
        challenge_id: str,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO enrolment_requests(
                    request_id, invite_id, node_id, node_name,
                    identity_public_key, csr_pem, advertised_host, peer_port,
                    protocol_version, status, receipt_digest, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'AWAITING_APPROVAL', ?, ?)
                """,
                (
                    request_id,
                    invite_id,
                    node_id,
                    node_name,
                    identity_public_key,
                    csr_pem,
                    advertised_host,
                    peer_port,
                    protocol_version,
                    receipt_digest,
                    created_at,
                ),
            )
            changed = self.connection.execute(
                """
                UPDATE enrolment_challenges SET used_at = ?
                WHERE challenge_id = ? AND used_at IS NULL
                """,
                (created_at, challenge_id),
            ).rowcount
            if changed != 1:
                raise sqlite3.IntegrityError("Enrolment challenge was already used")

    def get_enrolment_request(self, request_id: str) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM enrolment_requests WHERE request_id = ?", (request_id,)
        ).fetchone()

    def get_enrolment_by_node(self, node_id: str) -> sqlite3.Row | None:
        return self.connection.execute(
            """
            SELECT * FROM enrolment_requests
            WHERE node_id = ? AND status IN ('AWAITING_APPROVAL', 'APPROVED')
            ORDER BY created_at DESC LIMIT 1
            """,
            (node_id,),
        ).fetchone()

    def get_node(self, node_id: str) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM nodes WHERE node_id = ?", (node_id,)
        ).fetchone()

    def get_enrolment_by_receipt(self, receipt_digest: bytes) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM enrolment_requests WHERE receipt_digest = ?", (receipt_digest,)
        ).fetchone()

    def list_pending_enrolments(self) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT request_id, node_id, node_name, advertised_host, peer_port,
                       created_at, identity_public_key
                FROM enrolment_requests
                WHERE status = 'AWAITING_APPROVAL'
                ORDER BY created_at
                """
            )
        )

    def approve_enrolment(
        self,
        *,
        request_id: str,
        certificate_serial: str,
        certificate_pem: bytes,
        ca_certificate_pem: bytes,
        grant_public_key: bytes,
        decided_at: str,
    ) -> None:
        with self.connection:
            request = self.get_enrolment_request(request_id)
            if request is None or request["status"] != "AWAITING_APPROVAL":
                raise sqlite3.IntegrityError("Enrolment request is not pending")
            invite = self.connection.execute(
                "SELECT * FROM enrolment_invites WHERE invite_id = ?",
                (request["invite_id"],),
            ).fetchone()
            if invite is None or invite["consumed_at"] is not None:
                raise sqlite3.IntegrityError("Invitation is unavailable")
            self.connection.execute(
                """
                INSERT INTO nodes(
                    node_id, name, identity_public_key, advertised_host, peer_port,
                    status, certificate_serial, created_at, approved_at
                ) VALUES (?, ?, ?, ?, ?, 'APPROVED', ?, ?, ?)
                """,
                (
                    request["node_id"],
                    request["node_name"],
                    request["identity_public_key"],
                    request["advertised_host"],
                    request["peer_port"],
                    certificate_serial,
                    request["created_at"],
                    decided_at,
                ),
            )
            self.connection.execute(
                """
                UPDATE enrolment_requests
                SET status = 'APPROVED', decided_at = ?, certificate_pem = ?,
                    ca_certificate_pem = ?, grant_public_key = ?
                WHERE request_id = ?
                """,
                (
                    decided_at,
                    certificate_pem,
                    ca_certificate_pem,
                    grant_public_key,
                    request_id,
                ),
            )
            self.connection.execute(
                "UPDATE enrolment_invites SET consumed_at = ? WHERE invite_id = ?",
                (decided_at, request["invite_id"]),
            )

    def reject_enrolment(self, request_id: str, decided_at: str) -> bool:
        with self.connection:
            changed = self.connection.execute(
                """
                UPDATE enrolment_requests
                SET status = 'REJECTED', decided_at = ?
                WHERE request_id = ? AND status = 'AWAITING_APPROVAL'
                """,
                (decided_at, request_id),
            ).rowcount
        return changed == 1

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> CoordinatorRepository:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
