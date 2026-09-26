"""Minimal admission-only WSS relay boundary."""

from __future__ import annotations

import asyncio
import secrets
from datetime import UTC, datetime
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .api_models import decode_binary, encode_binary
from .crypto import load_public_key
from .grants import canonical_relay_ticket
from .models import RelayTicket


def create_relay_app(grant_public_key: bytes, *, max_frame_size: int = 1024 * 1024) -> FastAPI:
    app = FastAPI(title="barnCompute relay")
    peers: dict[tuple[str, str], WebSocket] = {}

    def validate(payload: dict[str, object], node_id: UUID) -> RelayTicket:
        payload = dict(payload)
        payload["signature"] = decode_binary(str(payload["signature"]))
        ticket = RelayTicket.model_validate(payload)
        if node_id not in (ticket.source_node_id, ticket.recipient_node_id):
            raise ValueError("node is not a ticket peer")
        now = datetime.now(UTC)
        if now < ticket.issued_at or now >= ticket.expires_at:
            raise ValueError("ticket is expired")
        load_public_key(grant_public_key).verify(
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

    return app
