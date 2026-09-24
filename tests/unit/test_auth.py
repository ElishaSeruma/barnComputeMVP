from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from barn_compute.auth import (
    NonceStore,
    SignedRequest,
    canonical_request,
    canonical_target,
    sign_request,
    verify_request,
)
from barn_compute.errors import BarnError, ErrorCode


def test_canonical_target_sorts_query_and_preserves_blank_values() -> None:
    assert canonical_target("/v1/files?z=3&a=&a=2") == "/v1/files?a=&a=2&z=3"


def test_canonical_request_has_stable_vector() -> None:
    assert canonical_request(
        "post",
        "/v1/files?b=2&a=1",
        "2026-01-02T03:04:05Z",
        "fixed-nonce",
        b'{"ok":true}',
    ).decode() == (
        "barn-request-v1\n"
        "POST\n"
        "/v1/files?a=1&b=2\n"
        "2026-01-02T03:04:05Z\n"
        "fixed-nonce\n"
        "4062edaf750fb8074e7e83e0c9028c94e32468a8b6f1614774328ef045150f93"
    )


def test_signature_verification_and_replay_rejection(tmp_path) -> None:
    key = Ed25519PrivateKey.generate()
    now = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    timestamp = now.isoformat().replace("+00:00", "Z")
    request = SignedRequest(
        method="GET",
        target="/v1/nodes",
        timestamp=timestamp,
        nonce="nonce-1",
        signature=sign_request(key, "GET", "/v1/nodes", timestamp, "nonce-1"),
    )
    with NonceStore(tmp_path / "nonces.db") as store:
        verify_request(key.public_key(), request, "node-a", store, now=now)
        with pytest.raises(BarnError) as replay:
            verify_request(key.public_key(), request, "node-a", store, now=now)
    assert replay.value.code == ErrorCode.REPLAY_DETECTED


def test_invalid_signature_does_not_consume_nonce(tmp_path) -> None:
    key = Ed25519PrivateKey.generate()
    attacker = Ed25519PrivateKey.generate()
    now = datetime.now(UTC)
    timestamp = now.isoformat()
    request = SignedRequest(
        method="GET",
        target="/v1/nodes",
        timestamp=timestamp,
        nonce="safe-to-retry",
        signature=sign_request(attacker, "GET", "/v1/nodes", timestamp, "safe-to-retry"),
    )
    with NonceStore(tmp_path / "nonces.db") as store:
        with pytest.raises(BarnError) as invalid:
            verify_request(key.public_key(), request, "node-a", store, now=now)
        assert invalid.value.code == ErrorCode.NOT_AUTHENTICATED

        valid = SignedRequest(
            method=request.method,
            target=request.target,
            timestamp=request.timestamp,
            nonce=request.nonce,
            signature=sign_request(
                key, request.method, request.target, request.timestamp, request.nonce
            ),
        )
        verify_request(key.public_key(), valid, "node-a", store, now=now)


def test_clock_skew_is_rejected(tmp_path) -> None:
    key = Ed25519PrivateKey.generate()
    now = datetime.now(UTC)
    old = now - timedelta(minutes=3)
    timestamp = old.isoformat()
    request = SignedRequest(
        method="GET",
        target="/v1/nodes",
        timestamp=timestamp,
        nonce="old",
        signature=sign_request(key, "GET", "/v1/nodes", timestamp, "old"),
    )
    with NonceStore(tmp_path / "nonces.db") as store, pytest.raises(BarnError) as error:
        verify_request(key.public_key(), request, "node-a", store, now=now)
    assert error.value.code == ErrorCode.CLOCK_SKEW
