"""SQLite persistence for coordinator-owned state."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = 1


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
                    decided_at TEXT
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
                """
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

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> CoordinatorRepository:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
