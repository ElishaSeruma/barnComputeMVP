"""Minimal admission-only WSS relay boundary."""

from __future__ import annotations

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
    peers: dict[str, WebSocket] = {}

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
                ticket.ticket_id, ticket.barn_id, ticket.source_node_id,
                ticket.recipient_node_id, ticket.issued_at, ticket.expires_at,
            ),
        )
        return ticket

    @app.websocket("/v1/tunnel")
    async def tunnel(websocket: WebSocket) -> None:
        await websocket.accept()
        registered: str | None = None
        try:
            hello = await websocket.receive_json()
            node_id = UUID(str(hello["node_id"]))
            ticket = validate(dict(hello["ticket"]), node_id)
            registered = str(node_id)
            peers[registered] = websocket
            await websocket.send_json({"type": "admitted", "ticket_id": str(ticket.ticket_id)})
            while True:
                message = await websocket.receive_json()
                if message.get("type") != "frame":
                    await websocket.close(code=1008)
                    return
                payload = decode_binary(str(message.get("payload", "")))
                if len(payload) > max_frame_size:
                    await websocket.close(code=1009)
                    return
                target = peers.get(str(message.get("recipient_node_id")))
                if target is not None:
                    await target.send_json({"type": "frame", "payload": encode_binary(payload)})
        except (KeyError, TypeError, ValueError, InvalidSignature):
            await websocket.close(code=1008)
        except WebSocketDisconnect:
            pass
        finally:
            if registered is not None and peers.get(registered) is websocket:
                del peers[registered]

    return app
