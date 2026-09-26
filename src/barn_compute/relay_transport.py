"""Bounded relay RPC with authenticated ephemeral sessions and replay protection."""

from __future__ import annotations

import json
import ssl
import struct
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from websockets.sync.client import connect

from .api_models import decode_binary, encode_binary
from .crypto import load_private_identity, load_public_key
from .errors import BarnError, ErrorCode
from .grants import canonical_relay_ticket
from .models import FileManifest, RelayTicket, TransferGrant
from .node.authority import PeerAuthority
from .node.service import NodeService
from .session import (
    SessionCipher,
    SessionHello,
    SessionKeyPair,
    create_session_hello,
    verify_session_hello,
)

MAX_PACKET = 2 * 1024 * 1024


class RelayConnection:
    def __init__(
        self, url: str, node: NodeService, ticket_payload: dict, *, ca: Path | None = None
    ):
        if not url.startswith("wss://"):
            raise BarnError(ErrorCode.CONFIGURATION, "Relay URL must use WSS")
        self.node = node
        payload = dict(ticket_payload)
        payload["signature"] = decode_binary(payload["signature"])
        self.ticket = RelayTicket.model_validate(payload)
        ticket = self.ticket
        metadata = node.load_metadata()
        if ticket.barn_id != metadata.barn_id or metadata.node_id not in (
            ticket.source_node_id,
            ticket.recipient_node_id,
        ):
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Relay ticket scope is invalid")
        now = datetime.now(UTC)
        if ticket.issued_at.tzinfo is None or not ticket.issued_at <= now < ticket.expires_at:
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Relay ticket expired")
        self.transcript = canonical_relay_ticket(
            ticket.ticket_id,
            ticket.barn_id,
            ticket.source_node_id,
            ticket.recipient_node_id,
            ticket.issued_at,
            ticket.expires_at,
            ticket.source_identity_key,
            ticket.recipient_identity_key,
        )
        load_public_key((node.state_dir / "grant-public.key").read_bytes()).verify(
            ticket.signature, self.transcript
        )
        self.source = metadata.node_id == ticket.source_node_id
        self.other = ticket.recipient_node_id if self.source else ticket.source_node_id
        context = ssl.create_default_context(cafile=str(ca) if ca else None)
        self.socket = connect(
            url,
            ssl=context,
            open_timeout=10,
            close_timeout=2,
            max_size=MAX_PACKET,
            max_queue=4,
            proxy=None,
        )
        try:
            challenge = self._json()
            if challenge["type"] != "challenge":
                raise ValueError("Relay challenge is required")
            proof = load_private_identity(node.state_dir / "secrets" / "identity-key.pem").sign(
                b"barn-relay-admission-v1\n"
                + str(ticket.ticket_id).encode()
                + b"\n"
                + str(metadata.node_id).encode()
                + b"\n"
                + challenge["nonce"].encode()
            )
            self.socket.send(
                json.dumps(
                    {
                        "node_id": str(metadata.node_id),
                        "ticket": ticket_payload,
                        "proof": encode_binary(proof),
                    }
                )
            )
            if self._json()["type"] != "admitted" or self._json()["type"] != "ready":
                raise ValueError("Relay pairing failed")
        except BaseException:
            self.socket.close()
            raise
        self.tx_sequence = self.rx_sequence = 0
        self.buffer = bytearray()

    def _json(self) -> dict:
        return json.loads(self.socket.recv(timeout=15))

    def close(self) -> None:
        self.socket.close()

    def _send(self, data: bytes) -> None:
        if len(data) > MAX_PACKET:
            raise ValueError("Relay packet exceeds limit")
        framed = struct.pack("!I", len(data)) + data
        for offset in range(0, len(framed), 64 * 1024):
            self.socket.send(
                json.dumps(
                    {
                        "type": "frame",
                        "recipient_node_id": str(self.other),
                        "payload": encode_binary(framed[offset : offset + 64 * 1024]),
                    }
                )
            )

    def _receive(self) -> bytes:
        while True:
            if len(self.buffer) >= 4:
                length = struct.unpack("!I", self.buffer[:4])[0]
                if length > MAX_PACKET:
                    raise ValueError("Relay packet exceeds limit")
                if len(self.buffer) >= length + 4:
                    data = bytes(self.buffer[4 : length + 4])
                    del self.buffer[: length + 4]
                    return data
            value = self._json()
            if value["type"] != "frame":
                raise ValueError("Unexpected relay frame")
            self.buffer.extend(decode_binary(value["payload"]))
            if len(self.buffer) > MAX_PACKET + 65540:
                raise ValueError("Relay receive buffer exceeded")

    def handshake(self, peer_identity: bytes) -> None:
        ephemeral = SessionKeyPair.generate()
        identity = load_private_identity(self.node.state_dir / "secrets" / "identity-key.pem")
        if self.source:
            peer = self._receive_hello(peer_identity, self.transcript)
            hello = create_session_hello(
                self.node.load_metadata().node_id,
                ephemeral,
                identity,
                transcript=self.transcript + peer.ephemeral_public_key,
            )
            self._send_hello(hello)
            transcript = self.transcript + peer.ephemeral_public_key + hello.ephemeral_public_key
        else:
            hello = create_session_hello(
                self.node.load_metadata().node_id, ephemeral, identity, transcript=self.transcript
            )
            self._send_hello(hello)
            peer = self._receive_hello(peer_identity, self.transcript + hello.ephemeral_public_key)
            transcript = self.transcript + hello.ephemeral_public_key + peer.ephemeral_public_key
        shared = ephemeral.private_key.exchange(
            X25519PublicKey.from_public_bytes(peer.ephemeral_public_key)
        )
        keys = HKDF(
            algorithm=hashes.SHA256(),
            length=64,
            salt=None,
            info=b"barn-relay-duplex-v1" + transcript,
        ).derive(shared)
        source_key, recipient_key = keys[:32], keys[32:]
        self.tx = SessionCipher(source_key if self.source else recipient_key)
        self.rx = SessionCipher(recipient_key if self.source else source_key)

    def _send_hello(self, hello: SessionHello) -> None:
        self._send(
            json.dumps(
                {
                    "node_id": str(hello.node_id),
                    "key": encode_binary(hello.ephemeral_public_key),
                    "signature": encode_binary(hello.signature),
                }
            ).encode()
        )

    def _receive_hello(self, peer_identity: bytes, transcript: bytes) -> SessionHello:
        value = json.loads(self._receive())
        hello = SessionHello(
            UUID(value["node_id"]), decode_binary(value["key"]), decode_binary(value["signature"])
        )
        if hello.node_id != self.other or len(hello.ephemeral_public_key) != 32:
            raise ValueError("Inner peer identity does not match ticket")
        verify_session_hello(hello, load_public_key(peer_identity), transcript=transcript)
        return hello

    def send(self, value: dict) -> None:
        aad = self.transcript + self.tx_sequence.to_bytes(8, "big")
        self._send(
            self.tx.seal(json.dumps(value, separators=(",", ":")).encode(), associated_data=aad)
        )
        self.tx_sequence += 1

    def receive(self) -> dict:
        aad = self.transcript + self.rx_sequence.to_bytes(8, "big")
        value = json.loads(self.rx.open(self._receive(), associated_data=aad))
        self.rx_sequence += 1
        return value


def serve_relay_transfer(connection: RelayConnection, authority: PeerAuthority) -> None:
    try:
        connection.handshake(authority.coordinator.peer_key(authority.node, connection.other))
        while True:
            request = connection.receive()
            if request.get("operation") == "close":
                return
            payload = request["grant"]
            payload["signature"] = decode_binary(payload["signature"])
            grant = TransferGrant.model_validate(payload)
            if grant.recipient_node_id != connection.other:
                raise BarnError(ErrorCode.NOT_AUTHORISED, "Relay recipient does not match grant")
            authority.validate(grant)
            if request["operation"] == "manifest":
                value = authority.node.grant_manifest(grant).model_dump(mode="json")
            elif request["operation"] == "chunk":
                value = encode_binary(authority.node.read_grant_chunk(grant, int(request["index"])))
            else:
                raise ValueError("Unknown relay operation")
            connection.send({"value": value})
    except BarnError as exc:
        connection.send({"error": {"code": str(exc.code), "message": exc.message}})
    finally:
        connection.close()


def relay_download(
    connection: RelayConnection, authority: PeerAuthority, grant: dict, destination: Path
) -> Path:
    try:
        connection.handshake(authority.coordinator.peer_key(authority.node, connection.other))
        parsed = dict(grant)
        parsed["signature"] = decode_binary(parsed["signature"])
        model = TransferGrant.model_validate(parsed)
        if model.source_node_id != connection.other:
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Relay source does not match grant")

        def request(operation: str, **extra) -> object:
            connection.send({"operation": operation, "grant": grant, **extra})
            response = connection.receive()
            if "error" in response:
                raise BarnError(ErrorCode(response["error"]["code"]), response["error"]["message"])
            return response["value"]

        manifest = FileManifest.model_validate(request("manifest"))
        journal = authority.node.start_transfer(model, manifest)
        for chunk in manifest.chunks:
            if chunk.index not in journal.completed_chunks:
                journal = authority.node.accept_transfer_chunk(
                    model, manifest, chunk.index, decode_binary(request("chunk", index=chunk.index))
                )
        destination = authority.node.export_transfer(model, manifest, destination)
        connection.send({"operation": "close"})
        return destination
    finally:
        connection.close()
