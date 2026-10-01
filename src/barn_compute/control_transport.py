"""Authenticated end-to-end coordinator RPC over the public WSS relay."""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

import httpx
from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import FastAPI
from websockets.exceptions import WebSocketException
from websockets.sync.client import ClientConnection, connect

from .api_models import decode_binary, encode_binary
from .coordinator.service import CoordinatorService
from .crypto import load_private_identity, load_public_key
from .errors import BarnError, ErrorCode
from .grants import canonical_control_grant
from .models import ControlGrant
from .node.service import NodeService
from .session import (
    SessionCipher,
    SessionHello,
    SessionKeyPair,
    create_session_hello,
    verify_session_hello,
)

MAX_CONTROL_PACKET = 1024 * 1024


def control_url(relay_url: str, role: str) -> str:
    parsed = urlsplit(relay_url)
    if parsed.scheme != "wss" or not parsed.hostname or role not in ("node", "coordinator"):
        raise BarnError(ErrorCode.CONFIGURATION, "Relay control URL must use WSS")
    return urlunsplit((parsed.scheme, parsed.netloc, f"/v1/control/{role}", "", ""))


def control_grant_payload(grant: ControlGrant) -> dict[str, object]:
    payload = grant.model_dump(mode="json", exclude={"signature"})
    payload["signature"] = encode_binary(grant.signature)
    return payload


def parse_control_grant(payload: dict[str, object]) -> ControlGrant:
    value = dict(payload)
    value["signature"] = decode_binary(str(value["signature"]))
    return ControlGrant.model_validate(value)


def control_transcript(grant: ControlGrant, session_id: UUID) -> bytes:
    return canonical_control_grant(
        grant.grant_id,
        grant.barn_id,
        grant.node_id,
        grant.node_identity_key,
        grant.issued_at,
        grant.expires_at,
    ) + session_id.bytes


def _session_keys(ephemeral: SessionKeyPair, peer_key: bytes, transcript: bytes) -> bytes:
    shared = ephemeral.private_key.exchange(X25519PublicKey.from_public_bytes(peer_key))
    return HKDF(
        algorithm=hashes.SHA256(),
        length=64,
        salt=None,
        info=b"barn-control-duplex-v1" + transcript,
    ).derive(shared)


def _hello_payload(hello: SessionHello) -> bytes:
    return json.dumps(
        {
            "node_id": str(hello.node_id),
            "key": encode_binary(hello.ephemeral_public_key),
            "signature": encode_binary(hello.signature),
        },
        separators=(",", ":"),
    ).encode()


def _parse_hello(payload: bytes) -> SessionHello:
    value = json.loads(payload)
    return SessionHello(
        UUID(value["node_id"]), decode_binary(value["key"]), decode_binary(value["signature"])
    )


class ControlConnection:
    """One serialized node-to-coordinator RPC session through the relay."""

    def __init__(self, relay_url: str, node: NodeService, *, ca: Path | None = None) -> None:
        self.node = node
        self.socket: ClientConnection | None = None
        self.lock = threading.Lock()
        try:
            payload = json.loads((node.state_dir / "control-grant.json").read_text())
            self.grant_payload = payload
            self.grant = parse_control_grant(payload)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise BarnError(
                ErrorCode.CONFIGURATION,
                "Control grant is unavailable; restore direct coordinator access once",
            ) from exc
        metadata = node.load_metadata()
        now = datetime.now(UTC)
        if (
            self.grant.barn_id != metadata.barn_id
            or self.grant.node_id != metadata.node_id
            or not self.grant.issued_at <= now < self.grant.expires_at
        ):
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Control grant is invalid or expired")
        canonical = canonical_control_grant(
            self.grant.grant_id,
            self.grant.barn_id,
            self.grant.node_id,
            self.grant.node_identity_key,
            self.grant.issued_at,
            self.grant.expires_at,
        )
        try:
            load_public_key((node.state_dir / "grant-public.key").read_bytes()).verify(
                self.grant.signature, canonical
            )
        except InvalidSignature as exc:
            raise BarnError(
                ErrorCode.NOT_AUTHENTICATED, "Control grant signature is invalid"
            ) from exc
        context = ssl.create_default_context(cafile=str(ca) if ca else None)
        try:
            self.socket = connect(
                control_url(relay_url, "node"),
                ssl=context,
                open_timeout=30,
                close_timeout=2,
                max_size=MAX_CONTROL_PACKET * 2,
                max_queue=4,
                proxy=None,
            )
            challenge = self._json()
            if challenge.get("type") != "challenge":
                raise ValueError("Relay control challenge is required")
            identity = load_private_identity(node.state_dir / "secrets" / "identity-key.pem")
            proof = identity.sign(
                b"barn-control-node-admission-v1\n"
                + str(self.grant.grant_id).encode()
                + b"\n"
                + str(metadata.node_id).encode()
                + b"\n"
                + str(challenge["nonce"]).encode()
            )
            self.socket.send(
                json.dumps(
                    {
                        "node_id": str(metadata.node_id),
                        "grant": self.grant_payload,
                        "proof": encode_binary(proof),
                    }
                )
            )
            admitted = self._json()
            if admitted.get("type") == "unavailable":
                raise BarnError(
                    ErrorCode.CONFIGURATION, "Coordinator control endpoint is unavailable"
                )
            if admitted.get("type") != "admitted":
                raise ValueError("Relay control admission failed")
            self.session_id = UUID(str(admitted["session_id"]))
            base = control_transcript(self.grant, self.session_id)
            ephemeral = SessionKeyPair.generate()
            hello = create_session_hello(metadata.node_id, ephemeral, identity, transcript=base)
            self.socket.send(
                json.dumps({"type": "hello", "payload": encode_binary(_hello_payload(hello))})
            )
            response = self._json()
            if response.get("type") == "unavailable":
                raise BarnError(
                    ErrorCode.CONFIGURATION, "Coordinator control endpoint is unavailable"
                )
            if response.get("type") != "hello":
                raise ValueError("Coordinator control hello is required")
            peer = _parse_hello(decode_binary(str(response["payload"])))
            if peer.node_id != self.grant.barn_id:
                raise ValueError("Coordinator control identity is invalid")
            verify_session_hello(
                peer,
                load_public_key((node.state_dir / "grant-public.key").read_bytes()),
                transcript=base + hello.ephemeral_public_key,
            )
            transcript = base + hello.ephemeral_public_key + peer.ephemeral_public_key
            keys = _session_keys(ephemeral, peer.ephemeral_public_key, transcript)
            self.tx = SessionCipher(keys[:32])
            self.rx = SessionCipher(keys[32:])
            self.transcript = transcript
            self.tx_sequence = self.rx_sequence = 0
        except BarnError:
            self.close()
            raise
        except (
            InvalidSignature,
            InvalidTag,
            OSError,
            TimeoutError,
            ValueError,
            WebSocketException,
        ) as exc:
            self.close()
            raise BarnError(ErrorCode.CONFIGURATION, "Relay control connection failed") from exc

    def _json(self) -> dict[str, object]:
        if self.socket is None:
            raise ValueError("Control socket is closed")
        return json.loads(self.socket.recv(timeout=15))

    def close(self) -> None:
        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def request(
        self, method: str, target: str, headers: dict[str, str], body: bytes
    ) -> httpx.Response:
        if len(body) > MAX_CONTROL_PACKET:
            raise BarnError(ErrorCode.INVALID_REQUEST, "Control request exceeds limit")
        with self.lock:
            if self.socket is None:
                raise BarnError(ErrorCode.CONFIGURATION, "Relay control connection is closed")
            value = {
                "method": method,
                "target": target,
                "headers": headers,
                "body": encode_binary(body),
            }
            aad = self.transcript + self.tx_sequence.to_bytes(8, "big")
            sealed = self.tx.seal(
                json.dumps(value, separators=(",", ":")).encode(), associated_data=aad
            )
            self.tx_sequence += 1
            try:
                self.socket.send(
                    json.dumps({"type": "frame", "payload": encode_binary(sealed)})
                )
                response = self._json()
                if response.get("type") == "unavailable":
                    raise BarnError(
                        ErrorCode.CONFIGURATION, "Coordinator control endpoint is unavailable"
                    )
                if response.get("type") != "frame":
                    raise ValueError("Coordinator control response is invalid")
                aad = self.transcript + self.rx_sequence.to_bytes(8, "big")
                opened = self.rx.open(
                    decode_binary(str(response["payload"])), associated_data=aad
                )
                self.rx_sequence += 1
                result = json.loads(opened)
                request = httpx.Request(method, "https://coordinator.invalid" + target)
                return httpx.Response(
                    int(result["status"]),
                    headers=dict(result["headers"]),
                    content=decode_binary(result["body"]),
                    request=request,
                )
            except BarnError:
                self.close()
                raise
            except (
                InvalidSignature,
                InvalidTag,
                OSError,
                TimeoutError,
                ValueError,
                WebSocketException,
            ) as exc:
                self.close()
                raise BarnError(
                    ErrorCode.CONFIGURATION, "Coordinator control session failed"
                ) from exc


@dataclass
class _CoordinatorSession:
    grant: ControlGrant
    base: bytes
    tx: SessionCipher | None = None
    rx: SessionCipher | None = None
    transcript: bytes | None = None
    tx_sequence: int = 0
    rx_sequence: int = 0


async def _dispatch(app: FastAPI, request: dict[str, object]) -> dict[str, object]:
    method = str(request["method"]).upper()
    target = str(request["target"])
    body = decode_binary(str(request["body"]))
    if method not in ("GET", "POST") or not target.startswith("/v1/") or "://" in target:
        raise ValueError("Control request target is invalid")
    if len(body) > MAX_CONTROL_PACKET:
        raise ValueError("Control request exceeds limit")
    supplied = dict(request["headers"])
    headers = {
        str(key): str(value)
        for key, value in supplied.items()
        if str(key).lower().startswith("x-barn-") or str(key).lower() == "content-type"
    }
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport, base_url="https://coordinator.invalid"
    ) as client:
        response = await client.request(method, target, headers=headers, content=body)
    if len(response.content) > MAX_CONTROL_PACKET:
        raise ValueError("Control response exceeds limit")
    return {
        "status": response.status_code,
        "headers": {"content-type": response.headers.get("content-type", "")},
        "body": encode_binary(response.content),
    }


def _run_coordinator_connection(
    service: CoordinatorService,
    app: FastAPI,
    relay_url: str,
    ca: Path | None,
    stop: threading.Event,
) -> None:
    metadata = service.load_metadata()
    grant_private = load_private_identity(service.state_dir / "secrets" / "grant-key.pem")
    grant_public = grant_private.public_key()
    context = ssl.create_default_context(cafile=str(ca) if ca else None)
    with connect(
        control_url(relay_url, "coordinator"),
        ssl=context,
        open_timeout=30,
        close_timeout=2,
        max_size=MAX_CONTROL_PACKET * 2,
        max_queue=16,
        proxy=None,
    ) as socket:
        challenge = json.loads(socket.recv(timeout=15))
        if challenge.get("type") != "challenge":
            raise ValueError("Relay coordinator challenge is required")
        proof = grant_private.sign(
            b"barn-control-coordinator-admission-v1\n"
            + str(metadata.barn_id).encode()
            + b"\n"
            + str(challenge["nonce"]).encode()
        )
        socket.send(json.dumps({"barn_id": str(metadata.barn_id), "proof": encode_binary(proof)}))
        if json.loads(socket.recv(timeout=15)).get("type") != "admitted":
            raise ValueError("Relay coordinator admission failed")
        sessions: dict[str, _CoordinatorSession] = {}
        while not stop.is_set():
            try:
                message = json.loads(socket.recv(timeout=1))
            except TimeoutError:
                continue
            session_id = str(UUID(str(message["session_id"])))
            if message["type"] == "open":
                grant = parse_control_grant(dict(message["grant"]))
                now = datetime.now(UTC)
                if (
                    grant.barn_id != metadata.barn_id
                    or not grant.issued_at <= now < grant.expires_at
                ):
                    raise ValueError("Control grant scope is invalid")
                grant_public.verify(
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
                sessions[session_id] = _CoordinatorSession(
                    grant=grant,
                    base=control_transcript(grant, UUID(session_id)),
                )
                continue
            if message["type"] == "close":
                sessions.pop(session_id, None)
                continue
            session = sessions.get(session_id)
            if session is None:
                socket.send(json.dumps({"type": "close", "session_id": session_id}))
                continue
            if message["type"] == "hello":
                peer = _parse_hello(decode_binary(str(message["payload"])))
                if peer.node_id != session.grant.node_id:
                    raise ValueError("Control node identity differs from grant")
                verify_session_hello(
                    peer,
                    load_public_key(decode_binary(session.grant.node_identity_key)),
                    transcript=session.base,
                )
                ephemeral = SessionKeyPair.generate()
                hello = create_session_hello(
                    metadata.barn_id,
                    ephemeral,
                    grant_private,
                    transcript=session.base + peer.ephemeral_public_key,
                )
                transcript = (
                    session.base + peer.ephemeral_public_key + hello.ephemeral_public_key
                )
                keys = _session_keys(ephemeral, peer.ephemeral_public_key, transcript)
                session.rx = SessionCipher(keys[:32])
                session.tx = SessionCipher(keys[32:])
                session.transcript = transcript
                socket.send(
                    json.dumps(
                        {
                            "type": "hello",
                            "session_id": session_id,
                            "payload": encode_binary(_hello_payload(hello)),
                        }
                    )
                )
                continue
            if message["type"] != "frame" or not all(
                (session.rx, session.tx, session.transcript)
            ):
                raise ValueError("Control session handshake is incomplete")
            aad = session.transcript + session.rx_sequence.to_bytes(8, "big")
            request = json.loads(
                session.rx.open(
                    decode_binary(str(message["payload"])), associated_data=aad
                )
            )
            session.rx_sequence += 1
            response = asyncio.run(_dispatch(app, request))
            aad = session.transcript + session.tx_sequence.to_bytes(8, "big")
            sealed = session.tx.seal(
                json.dumps(response, separators=(",", ":")).encode(), associated_data=aad
            )
            session.tx_sequence += 1
            socket.send(
                json.dumps(
                    {
                        "type": "frame",
                        "session_id": session_id,
                        "payload": encode_binary(sealed),
                    }
                )
            )


def run_coordinator_control(
    service: CoordinatorService,
    app: FastAPI,
    relay_url: str,
    ca: Path | None,
    stop: threading.Event,
) -> None:
    log = logging.getLogger(__name__)
    while not stop.is_set():
        try:
            _run_coordinator_connection(service, app, relay_url, ca, stop)
        except (
            InvalidSignature,
            InvalidTag,
            OSError,
            TimeoutError,
            ValueError,
            WebSocketException,
        ) as exc:
            if not stop.is_set():
                log.warning(
                    "Relay control connection failed at %s; retrying",
                    type(exc).__name__,
                )
        stop.wait(1)
