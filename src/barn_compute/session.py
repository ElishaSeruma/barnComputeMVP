"""Authenticated encrypted inner-session envelopes for relay transport."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from uuid import UUID

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


@dataclass(frozen=True)
class SessionKeyPair:
    private_key: X25519PrivateKey

    @classmethod
    def generate(cls) -> SessionKeyPair:
        return cls(X25519PrivateKey.generate())

    def public_bytes(self) -> bytes:
        return self.private_key.public_key().public_bytes_raw()

    def derive(self, peer_public_key: bytes, *, transcript: bytes = b"") -> SessionCipher:
        shared = self.private_key.exchange(X25519PublicKey.from_public_bytes(peer_public_key))
        key = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=None,
            info=b"barn-inner-session-v1" + transcript,
        ).derive(shared)
        return SessionCipher(key)


@dataclass(frozen=True)
class SessionHello:
    node_id: UUID
    ephemeral_public_key: bytes
    signature: bytes


def _handshake_bytes(node_id: UUID, ephemeral_public_key: bytes, transcript: bytes) -> bytes:
    return json.dumps(
        {
            "domain": "barn-inner-session-hello-v1",
            "node_id": str(node_id),
            "ephemeral_public_key": ephemeral_public_key.hex(),
            "transcript": transcript.hex(),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def create_session_hello(
    node_id: UUID,
    session_key_pair: SessionKeyPair,
    identity_key: Ed25519PrivateKey,
    *,
    transcript: bytes = b"",
) -> SessionHello:
    ephemeral_public_key = session_key_pair.public_bytes()
    signature = identity_key.sign(_handshake_bytes(node_id, ephemeral_public_key, transcript))
    return SessionHello(node_id, ephemeral_public_key, signature)


def verify_session_hello(
    hello: SessionHello,
    identity_public_key: Ed25519PublicKey,
    *,
    transcript: bytes = b"",
) -> None:
    identity_public_key.verify(
        hello.signature,
        _handshake_bytes(hello.node_id, hello.ephemeral_public_key, transcript),
    )


@dataclass
class SessionCipher:
    key: bytes

    def seal(self, plaintext: bytes, *, associated_data: bytes = b"") -> bytes:
        nonce = os.urandom(12)
        return nonce + ChaCha20Poly1305(self.key).encrypt(nonce, plaintext, associated_data)

    def open(self, envelope: bytes, *, associated_data: bytes = b"") -> bytes:
        if len(envelope) < 12 + 16:
            raise ValueError("Encrypted session envelope is too short")
        nonce, ciphertext = envelope[:12], envelope[12:]
        return ChaCha20Poly1305(self.key).decrypt(nonce, ciphertext, associated_data)
