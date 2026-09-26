"""Authenticated encrypted inner-session envelopes for relay transport."""

from __future__ import annotations

import os
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
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
