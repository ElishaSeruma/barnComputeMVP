"""Minimal admission-only WSS relay boundary."""

from __future__ import annotations

import asyncio
import secrets
from contextlib import suppress
from datetime import UTC, datetime
from uuid import UUID, uuid4

from cryptography.exceptions import InvalidSignature
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .api_models import decode_binary, encode_binary
from .crypto import load_public_key
from .grants import canonical_control_grant, canonical_relay_ticket
from .models import ControlGrant, RelayTicket


def create_relay_app(grant_public_key: bytes, *, max_frame_size: int = 1024 * 1024) -> FastAPI:
    app = FastAPI(title="barnCompute relay")
    peers: dict[tuple[str, str], WebSocket] = {}
    coordinators: dict[str, WebSocket] = {}
    coordinator_locks: dict[str, asyncio.Lock] = {}
    control_nodes: dict[tuple[str, str], WebSocket] = {}
    control_node_locks: dict[tuple[str, str], asyncio.Lock] = {}
    grant_key = load_public_key(grant_public_key)

    def validate(payload: dict[str, object], node_id: UUID) -> RelayTicket:
        payload = dict(payload)
        payload["signature"] = decode_binary(str(payload["signature"]))
        ticket = RelayTicket.model_validate(payload)
        if node_id not in (ticket.source_node_id, ticket.recipient_node_id):
            raise ValueError("node is not a ticket peer")
        now = datetime.now(UTC)
        if now < ticket.issued_at or now >= ticket.expires_at:
            raise ValueError("ticket is expired")
        grant_key.verify(
            ticket.signature,
            canonical_relay_ticket(
                ticket.ticket_id,
                ticket.barn_id,
                ticket.source_node_id,
                ticket.recipient_node_id,
                ticket.issued_at,
                ticket.expires_at,
                ticket.source_identity_key,
                ticket.recipient_identity_key,
            ),
        )
        return ticket

    def validate_control(payload: dict[str, object], node_id: UUID) -> ControlGrant:
        payload = dict(payload)
        payload["signature"] = decode_binary(str(payload["signature"]))
        grant = ControlGrant.model_validate(payload)
        if grant.node_id != node_id:
            raise ValueError("node is outside control grant scope")
        now = datetime.now(UTC)
        if now < grant.issued_at or now >= grant.expires_at:
            raise ValueError("control grant is expired")
        grant_key.verify(
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
        return grant

    @app.websocket("/v1/tunnel")
    async def tunnel(websocket: WebSocket) -> None:
        await websocket.accept()
        registered: tuple[str, str] | None = None
        try:
            challenge = secrets.token_hex(32)
            await websocket.send_json({"type": "challenge", "nonce": challenge})
            hello = await asyncio.wait_for(websocket.receive_json(), 10)
            node_id = UUID(str(hello["node_id"]))
            ticket = validate(dict(hello["ticket"]), node_id)
            identity = (
                ticket.source_identity_key
                if node_id == ticket.source_node_id
                else ticket.recipient_identity_key
            )
            load_public_key(decode_binary(identity)).verify(
                decode_binary(hello["proof"]),
                b"barn-relay-admission-v1\n"
                + str(ticket.ticket_id).encode()
                + b"\n"
                + str(node_id).encode()
                + b"\n"
                + challenge.encode(),
            )
            registered = (str(ticket.ticket_id), str(node_id))
            if len(peers) >= 64 or registered in peers:
                raise ValueError("Relay connection quota or duplicate peer")
            peers[registered] = websocket
            await websocket.send_json({"type": "admitted", "ticket_id": str(ticket.ticket_id)})
            other = (
                ticket.recipient_node_id
                if node_id == ticket.source_node_id
                else ticket.source_node_id
            )
            target_key = (str(ticket.ticket_id), str(other))
            target = peers.get(target_key)
            if target is not None:
                await target.send_json({"type": "ready"})
                await websocket.send_json({"type": "ready"})
            transferred = 0
            while True:
                remaining = (ticket.expires_at - datetime.now(UTC)).total_seconds()
                if remaining <= 0:
                    raise ValueError("Relay ticket expired")
                message = await asyncio.wait_for(websocket.receive_json(), min(remaining, 60))
                if message.get("type") != "frame":
                    await websocket.close(code=1008)
                    return
                payload = decode_binary(str(message.get("payload", "")))
                if len(payload) > max_frame_size:
                    await websocket.close(code=1009)
                    return
                if str(message.get("recipient_node_id")) != str(other):
                    raise ValueError("Relay target is outside ticket scope")
                transferred += len(payload)
                if transferred > 768 * 1024 * 1024:
                    raise ValueError("Relay session byte quota exceeded")
                target = peers.get(target_key)
                if target is None:
                    raise ValueError("Relay peer is disconnected")
                await asyncio.wait_for(
                    target.send_json({"type": "frame", "payload": encode_binary(payload)}), 10
                )
        except (KeyError, TypeError, ValueError, InvalidSignature, TimeoutError):
            await websocket.close(code=1008)
        except WebSocketDisconnect:
            pass
        finally:
            if registered is not None and peers.get(registered) is websocket:
                del peers[registered]

    @app.websocket("/v1/control/coordinator")
    async def control_coordinator(websocket: WebSocket) -> None:
        await websocket.accept()
        barn_id: str | None = None
        try:
            challenge = secrets.token_hex(32)
            await websocket.send_json({"type": "challenge", "nonce": challenge})
            hello = await asyncio.wait_for(websocket.receive_json(), 10)
            barn_id = str(UUID(str(hello["barn_id"])))
            grant_key.verify(
                decode_binary(str(hello["proof"])),
                b"barn-control-coordinator-admission-v1\n"
                + barn_id.encode()
                + b"\n"
                + challenge.encode(),
            )
            if len(coordinators) >= 16 or barn_id in coordinators:
                raise ValueError("Coordinator quota or duplicate connection")
            coordinators[barn_id] = websocket
            coordinator_locks[barn_id] = asyncio.Lock()
            await websocket.send_json({"type": "admitted", "barn_id": barn_id})
            while True:
                message = await websocket.receive_json()
                if message.get("type") not in ("hello", "frame", "close"):
                    raise ValueError("Unexpected coordinator control message")
                session_id = str(UUID(str(message["session_id"])))
                key = (barn_id, session_id)
                target = control_nodes.get(key)
                if target is None:
                    continue
                forwarded = {
                    "type": message["type"],
                    "session_id": session_id,
                }
                if message["type"] in ("hello", "frame"):
                    payload = str(message["payload"])
                    if len(decode_binary(payload)) > max_frame_size:
                        raise ValueError("Control frame exceeds limit")
                    forwarded["payload"] = payload
                async with control_node_locks[key]:
                    await asyncio.wait_for(target.send_json(forwarded), 10)
        except (KeyError, TypeError, ValueError, InvalidSignature, TimeoutError):
            await websocket.close(code=1008)
        except WebSocketDisconnect:
            pass
        finally:
            if barn_id is not None and coordinators.get(barn_id) is websocket:
                del coordinators[barn_id]
                coordinator_locks.pop(barn_id, None)
                for key, target in list(control_nodes.items()):
                    if key[0] == barn_id:
                        with suppress(RuntimeError, WebSocketDisconnect):
                            await target.send_json(
                                {"type": "unavailable", "reason": "coordinator"}
                            )

    @app.websocket("/v1/control/node")
    async def control_node(websocket: WebSocket) -> None:
        await websocket.accept()
        registered: tuple[str, str] | None = None
        coordinator: WebSocket | None = None
        try:
            challenge = secrets.token_hex(32)
            await websocket.send_json({"type": "challenge", "nonce": challenge})
            hello = await asyncio.wait_for(websocket.receive_json(), 10)
            node_id = UUID(str(hello["node_id"]))
            grant = validate_control(dict(hello["grant"]), node_id)
            load_public_key(decode_binary(grant.node_identity_key)).verify(
                decode_binary(str(hello["proof"])),
                b"barn-control-node-admission-v1\n"
                + str(grant.grant_id).encode()
                + b"\n"
                + str(node_id).encode()
                + b"\n"
                + challenge.encode(),
            )
            barn_id = str(grant.barn_id)
            coordinator = coordinators.get(barn_id)
            if coordinator is None:
                await websocket.send_json({"type": "unavailable", "reason": "coordinator"})
                await websocket.close(code=1013)
                return
            session_id = str(uuid4())
            registered = (barn_id, session_id)
            if len(control_nodes) >= 64:
                raise ValueError("Control connection quota exceeded")
            control_nodes[registered] = websocket
            control_node_locks[registered] = asyncio.Lock()
            await websocket.send_json({"type": "admitted", "session_id": session_id})
            async with coordinator_locks[barn_id]:
                await asyncio.wait_for(
                    coordinator.send_json(
                        {
                            "type": "open",
                            "session_id": session_id,
                            "grant": hello["grant"],
                        }
                    ),
                    10,
                )
            transferred = 0
            while True:
                message = await websocket.receive_json()
                if message.get("type") not in ("hello", "frame", "close"):
                    raise ValueError("Unexpected node control message")
                forwarded = {"type": message["type"], "session_id": session_id}
                if message["type"] in ("hello", "frame"):
                    payload = str(message["payload"])
                    decoded = decode_binary(payload)
                    if len(decoded) > max_frame_size:
                        raise ValueError("Control frame exceeds limit")
                    transferred += len(decoded)
                    if transferred > 64 * 1024 * 1024:
                        raise ValueError("Control session byte quota exceeded")
                    forwarded["payload"] = payload
                async with coordinator_locks[barn_id]:
                    await asyncio.wait_for(coordinator.send_json(forwarded), 10)
                if message["type"] == "close":
                    return
        except (KeyError, TypeError, ValueError, InvalidSignature, TimeoutError):
            await websocket.close(code=1008)
        except WebSocketDisconnect:
            pass
        finally:
            if registered is not None and control_nodes.get(registered) is websocket:
                del control_nodes[registered]
                control_node_locks.pop(registered, None)
                if coordinator is not None:
                    try:
                        async with coordinator_locks[registered[0]]:
                            await coordinator.send_json(
                                {"type": "close", "session_id": registered[1]}
                            )
                    except (KeyError, RuntimeError, WebSocketDisconnect):
                        pass

    return app
