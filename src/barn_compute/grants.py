"""Canonical transfer-grant signing input shared by coordinator and peers."""

from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID


def canonical_transfer_grant(
    grant_id: UUID,
    share_id: UUID,
    transfer_id: UUID,
    file_id: UUID,
    source_node_id: UUID,
    recipient_node_id: UUID,
    issued_at: datetime,
    expires_at: datetime,
) -> bytes:
    payload = {
        "domain": "barn-transfer-grant-v1",
        "grant_id": str(grant_id),
        "share_id": str(share_id),
        "transfer_id": str(transfer_id),
        "file_id": str(file_id),
        "source_node_id": str(source_node_id),
        "recipient_node_id": str(recipient_node_id),
        "issued_at": issued_at.isoformat().replace("+00:00", "Z"),
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_relay_ticket(
    ticket_id: UUID,
    barn_id: UUID,
    source_node_id: UUID,
    recipient_node_id: UUID,
    issued_at: datetime,
    expires_at: datetime,
    source_identity_key: str,
    recipient_identity_key: str,
) -> bytes:
    payload = {
        "domain": "barn-relay-ticket-v1",
        "source_identity_key": source_identity_key,
        "recipient_identity_key": recipient_identity_key,
        "ticket_id": str(ticket_id),
        "barn_id": str(barn_id),
        "source_node_id": str(source_node_id),
        "recipient_node_id": str(recipient_node_id),
        "issued_at": issued_at.isoformat().replace("+00:00", "Z"),
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_control_grant(
    grant_id: UUID,
    barn_id: UUID,
    node_id: UUID,
    node_identity_key: str,
    issued_at: datetime,
    expires_at: datetime,
) -> bytes:
    payload = {
        "domain": "barn-control-grant-v1",
        "grant_id": str(grant_id),
        "barn_id": str(barn_id),
        "node_id": str(node_id),
        "node_identity_key": node_identity_key,
        "issued_at": issued_at.isoformat().replace("+00:00", "Z"),
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
