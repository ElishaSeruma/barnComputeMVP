"""Canonical signed-request authentication and durable replay prevention."""

from __future__ import annotations

import base64
import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .errors import BarnError, ErrorCode

SIGNATURE_DOMAIN = b"barn-request-v1\n"
EMPTY_BODY_SHA256 = hashlib.sha256(b"").hexdigest()


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def canonical_target(target: str) -> str:
    parsed = urlsplit(target)
    path = quote(parsed.path or "/", safe="/%:@-._~!$&'()*+,;=")
    pairs = sorted(parse_qsl(parsed.query, keep_blank_values=True))
    query = urlencode(pairs, doseq=True, quote_via=quote, safe="~")
    return f"{path}?{query}" if query else path


def canonical_request(
    method: str,
    target: str,
    timestamp: str,
    nonce: str,
    body: bytes = b"",
) -> bytes:
    fields = (
        method.upper(),
        canonical_target(target),
        timestamp,
        nonce,
        hashlib.sha256(body).hexdigest(),
    )
    if any("\n" in field or "\r" in field for field in fields):
        raise BarnError(ErrorCode.INVALID_REQUEST, "Signed request fields cannot contain newlines")
    return SIGNATURE_DOMAIN + "\n".join(fields).encode("utf-8")


def sign_request(
    private_key: Ed25519PrivateKey,
    method: str,
    target: str,
    timestamp: str,
    nonce: str,
    body: bytes = b"",
) -> str:
    message = canonical_request(method, target, timestamp, nonce, body)
    return _b64url_encode(private_key.sign(message))


@dataclass(frozen=True, slots=True)
class SignedRequest:
    method: str
    target: str
    timestamp: str
    nonce: str
    signature: str
    body: bytes = b""


class NonceStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_nonces (
                node_id TEXT NOT NULL,
                nonce TEXT NOT NULL,
                accepted_at TEXT NOT NULL,
                PRIMARY KEY (node_id, nonce)
            )
            """
        )
        self._connection.commit()

    def accept(self, node_id: str, nonce: str, now: datetime, window: timedelta) -> None:
        cutoff = (now - window).isoformat()
        with self._connection:
            self._connection.execute("DELETE FROM auth_nonces WHERE accepted_at < ?", (cutoff,))
            try:
                self._connection.execute(
                    "INSERT INTO auth_nonces(node_id, nonce, accepted_at) VALUES (?, ?, ?)",
                    (node_id, nonce, now.isoformat()),
                )
            except sqlite3.IntegrityError as exc:
                raise BarnError(
                    ErrorCode.REPLAY_DETECTED, "Request nonce was already used"
                ) from exc

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> NonceStore:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def verify_request(
    public_key: Ed25519PublicKey,
    request: SignedRequest,
    node_id: str,
    nonce_store: NonceStore,
    *,
    now: datetime | None = None,
    maximum_skew: timedelta = timedelta(seconds=120),
) -> None:
    checked_at = now or datetime.now(UTC)
    try:
        sent_at = datetime.fromisoformat(request.timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BarnError(ErrorCode.INVALID_REQUEST, "Timestamp must be RFC 3339") from exc
    if sent_at.tzinfo is None:
        raise BarnError(ErrorCode.INVALID_REQUEST, "Timestamp must include a UTC offset")
    sent_at = sent_at.astimezone(UTC)
    if abs(checked_at - sent_at) > maximum_skew:
        raise BarnError(ErrorCode.CLOCK_SKEW, "Request timestamp is outside the allowed window")
    try:
        signature = _b64url_decode(request.signature)
        public_key.verify(
            signature,
            canonical_request(
                request.method,
                request.target,
                request.timestamp,
                request.nonce,
                request.body,
            ),
        )
    except (InvalidSignature, ValueError) as exc:
        raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Request signature is invalid") from exc
    nonce_store.accept(node_id, request.nonce, checked_at, maximum_skew)
