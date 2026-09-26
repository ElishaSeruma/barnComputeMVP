from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from barn_compute.auth import SignedRequest, sign_request
from barn_compute.coordinator.app import create_public_app
from barn_compute.coordinator.service import CoordinatorService
from barn_compute.crypto import load_private_identity
from barn_compute.errors import BarnError, ErrorCode
from barn_compute.models import NodeStatus
from barn_compute.node.service import NodeService


def approved_pair(tmp_path):
    coordinator = CoordinatorService(tmp_path / "coordinator")
    coordinator_metadata = coordinator.initialize("LabBarn", "127.0.0.1")
    node = NodeService(tmp_path / "node")
    node.initialize("NodeA", "127.0.0.2")
    node.pin_barn_ca(
        (coordinator.state_dir / "ca-cert.pem").read_bytes(),
        coordinator_metadata.ca_fingerprint,
    )
    invite = coordinator.create_invite(timedelta(minutes=10))
    metadata = node.load_metadata()
    challenge = coordinator.create_enrolment_challenge(invite.code, str(metadata.node_id))
    receipt = coordinator.submit_enrolment(invite.code, node.create_submission(challenge))
    node.record_receipt(receipt.request_id, receipt.receipt)
    node.complete_enrolment(coordinator.approve_enrolment(str(receipt.request_id)))
    return coordinator, node


def signed(node, method: str, target: str, body: bytes, now: datetime, nonce: str):
    timestamp = now.isoformat().replace("+00:00", "Z")
    key = load_private_identity(node.state_dir / "secrets" / "identity-key.pem")
    return SignedRequest(
        method=method,
        target=target,
        timestamp=timestamp,
        nonce=nonce,
        signature=sign_request(key, method, target, timestamp, nonce, body),
        body=body,
    )


def test_signed_heartbeat_and_liveness_transitions(tmp_path) -> None:
    coordinator, node = approved_pair(tmp_path)
    now = datetime.now(UTC)
    heartbeat = node.next_heartbeat().model_copy(update={"sent_at": now})
    body = heartbeat.model_dump_json().encode()
    coordinator.accept_heartbeat(
        heartbeat,
        signed(node, "POST", "/v1/heartbeat", body, now, "heartbeat-1"),
        now=now,
    )

    metadata = node.load_metadata()
    online = coordinator.list_registered_nodes(
        str(metadata.node_id),
        signed(node, "GET", "/v1/nodes", b"", now, "registry-online"),
        now=now,
    )
    assert online[0].status is NodeStatus.ONLINE

    suspect_at = now + timedelta(seconds=46)
    suspect = coordinator.list_registered_nodes(
        str(metadata.node_id),
        signed(node, "GET", "/v1/nodes", b"", suspect_at, "registry-suspect"),
        now=suspect_at,
    )
    assert suspect[0].status is NodeStatus.SUSPECT

    offline_at = now + timedelta(seconds=121)
    offline = coordinator.list_registered_nodes(
        str(metadata.node_id),
        signed(node, "GET", "/v1/nodes", b"", offline_at, "registry-offline"),
        now=offline_at,
    )
    assert offline[0].status is NodeStatus.OFFLINE


def test_heartbeat_replay_and_sequence_rollback_are_rejected(tmp_path) -> None:
    coordinator, node = approved_pair(tmp_path)
    now = datetime.now(UTC)
    heartbeat = node.next_heartbeat().model_copy(update={"sent_at": now})
    body = heartbeat.model_dump_json().encode()
    request = signed(node, "POST", "/v1/heartbeat", body, now, "same-nonce")
    coordinator.accept_heartbeat(heartbeat, request, now=now)

    with pytest.raises(BarnError) as replay:
        coordinator.accept_heartbeat(heartbeat, request, now=now)
    assert replay.value.code is ErrorCode.REPLAY_DETECTED

    rollback_request = signed(
        node, "POST", "/v1/heartbeat", body, now, "new-nonce"
    )
    with pytest.raises(BarnError) as rollback:
        coordinator.accept_heartbeat(heartbeat, rollback_request, now=now)
    assert rollback.value.code is ErrorCode.REPLAY_DETECTED


def test_unapproved_node_cannot_create_heartbeat(tmp_path) -> None:
    node = NodeService(tmp_path / "node")
    node.initialize("NodeA", "127.0.0.2")
    with pytest.raises(BarnError) as error:
        node.next_heartbeat()
    assert error.value.code is ErrorCode.NOT_AUTHORISED


def test_heartbeat_and_registry_http_routes_verify_exact_body(tmp_path) -> None:
    coordinator, node = approved_pair(tmp_path)
    client = TestClient(create_public_app(coordinator))
    heartbeat = node.next_heartbeat()
    body = heartbeat.model_dump_json().encode()
    now = datetime.now(UTC)
    request = signed(node, "POST", "/v1/heartbeat", body, now, "http-heartbeat")
    response = client.post(
        "/v1/heartbeat",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Barn-Timestamp": request.timestamp,
            "X-Barn-Nonce": request.nonce,
            "X-Barn-Signature": request.signature,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ONLINE"

    metadata = node.load_metadata()
    registry_request = signed(node, "GET", "/v1/nodes", b"", now, "http-registry")
    registry = client.get(
        "/v1/nodes",
        headers={
            "X-Barn-Node-ID": str(metadata.node_id),
            "X-Barn-Timestamp": registry_request.timestamp,
            "X-Barn-Nonce": registry_request.nonce,
            "X-Barn-Signature": registry_request.signature,
        },
    )
    assert registry.status_code == 200
    assert registry.json()["nodes"][0]["status"] == "ONLINE"
