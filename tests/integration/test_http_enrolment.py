from datetime import timedelta
from uuid import UUID

from fastapi.testclient import TestClient

from barn_compute.api_models import decode_binary, encode_binary
from barn_compute.control_transport import parse_control_grant
from barn_compute.coordinator.admin import create_admin_app
from barn_compute.coordinator.app import create_public_app
from barn_compute.coordinator.service import CoordinatorService
from barn_compute.models import (
    EnrolmentChallenge,
    EnrolmentResult,
    EnrolmentStatus,
    NodeStatus,
)
from barn_compute.node.app import create_local_app, create_peer_app
from barn_compute.node.service import NodeService


def setup_http_flow(tmp_path):
    coordinator = CoordinatorService(tmp_path / "coordinator")
    coordinator_metadata = coordinator.initialize("LabBarn", "127.0.0.1")
    node = NodeService(tmp_path / "node")
    node.initialize("MacNode", "127.0.0.2")
    ca_pem = (coordinator.state_dir / "ca-cert.pem").read_bytes()
    node.pin_barn_ca(ca_pem, coordinator_metadata.ca_fingerprint)
    public = TestClient(create_public_app(coordinator))
    admin = TestClient(create_admin_app(coordinator, "admin-test-token"))
    admin_headers = {"Authorization": "Bearer admin-test-token"}
    return coordinator, node, public, admin, admin_headers


def test_complete_enrolment_through_separate_public_and_admin_apis(tmp_path) -> None:
    _coordinator, node, public, admin, admin_headers = setup_http_flow(tmp_path)

    invite_response = admin.post(
        "/local/v1/invites",
        json={"ttl_seconds": 600},
        headers=admin_headers,
    )
    assert invite_response.status_code == 200
    invite = invite_response.json()
    metadata = node.load_metadata()

    challenge_response = public.post(
        "/v1/enrolments/challenge",
        json={"invite_code": invite["code"], "node_id": str(metadata.node_id)},
    )
    assert challenge_response.status_code == 200
    challenge = challenge_response.json()
    submission = node.create_submission(EnrolmentChallenge.model_validate(challenge))
    payload = {
        "invite_code": invite["code"],
        "node_id": str(metadata.node_id),
        "node_name": metadata.name,
        "advertised_host": metadata.advertised_host,
        "peer_port": metadata.peer_port,
        "protocol_version": submission.protocol_version,
        "identity_public_key": encode_binary(submission.identity_public_key),
        "csr_pem": encode_binary(submission.csr_pem),
        "challenge": challenge["challenge"],
        "proof": encode_binary(submission.proof),
    }
    submitted = public.post("/v1/enrolments", json=payload)
    assert submitted.status_code == 202
    receipt = submitted.json()
    node.record_receipt(UUID(receipt["request_id"]), receipt["receipt"])

    assert public.get(f"/v1/enrolments/{receipt['request_id']}").status_code == 401
    pending = public.get(
        f"/v1/enrolments/{receipt['request_id']}",
        headers={"X-Barn-Enrolment-Receipt": receipt["receipt"]},
    )
    assert pending.json()["status"] == "AWAITING_APPROVAL"

    assert admin.get("/local/v1/enrolments").status_code == 401
    listed = admin.get("/local/v1/enrolments", headers=admin_headers)
    assert listed.status_code == 200
    assert [item["request_id"] for item in listed.json()] == [receipt["request_id"]]

    approved = admin.post(
        f"/local/v1/enrolments/{receipt['request_id']}/approve",
        headers=admin_headers,
    )
    assert approved.status_code == 200
    result_response = public.get(
        f"/v1/enrolments/{receipt['request_id']}",
        headers={"X-Barn-Enrolment-Receipt": receipt["receipt"]},
    )
    result_payload = result_response.json()
    result = EnrolmentResult(
        request_id=result_payload["request_id"],
        status=result_payload["status"],
        barn_id=result_payload["barn_id"],
        certificate_pem=decode_binary(result_payload["certificate_pem"]),
        ca_certificate_pem=decode_binary(result_payload["ca_certificate_pem"]),
        grant_public_key=decode_binary(result_payload["grant_public_key"]),
        control_grant=parse_control_grant(result_payload["control_grant"]),
        decided_at=result_payload["decided_at"],
    )
    assert node.complete_enrolment(result).status is NodeStatus.APPROVED
    assert (node.state_dir / "control-grant.json").is_file()

    peer = TestClient(create_peer_app(node))
    local = TestClient(create_local_app(node, "node-admin-token"))
    assert peer.get("/v1/health").status_code == 200
    assert local.get("/local/v1/status").status_code == 401
    assert (
        local.get(
            "/local/v1/status",
            headers={"Authorization": "Bearer node-admin-token"},
        ).json()["status"]
        == "APPROVED"
    )


def test_http_errors_are_bounded_and_do_not_echo_secrets(tmp_path) -> None:
    _coordinator, node, public, admin, admin_headers = setup_http_flow(tmp_path)
    secret = "this-secret-must-not-be-echoed"
    response = public.post(
        "/v1/enrolments/challenge",
        json={"invite_code": secret, "node_id": str(node.load_metadata().node_id)},
    )
    assert response.status_code == 401
    assert secret not in response.text
    assert set(response.json()["error"]) == {"code", "message", "request_id"}

    malformed = public.post(
        "/v1/enrolments/challenge",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert malformed.status_code == 400
    assert malformed.json()["error"]["code"] == "INVALID_REQUEST"

    oversized = public.post(
        "/v1/enrolments/challenge",
        content=b"x",
        headers={"Content-Length": str(65 * 1024)},
    )
    assert oversized.status_code == 413

    wrong_admin = admin.get(
        "/local/v1/enrolments",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert wrong_admin.status_code == 401
    assert admin.get("/local/v1/status", headers=admin_headers).status_code == 200


def test_admin_can_reject_without_exposing_result_material(tmp_path) -> None:
    coordinator, node, public, admin, admin_headers = setup_http_flow(tmp_path)
    invite = coordinator.create_invite(timedelta(minutes=10))
    metadata = node.load_metadata()
    challenge = coordinator.create_enrolment_challenge(invite.code, str(metadata.node_id))
    submission = node.create_submission(challenge)
    receipt = coordinator.submit_enrolment(invite.code, submission)

    response = admin.post(
        f"/local/v1/enrolments/{receipt.request_id}/reject",
        headers=admin_headers,
    )
    assert response.status_code == 204
    result = public.get(
        f"/v1/enrolments/{receipt.request_id}",
        headers={"X-Barn-Enrolment-Receipt": receipt.receipt},
    ).json()
    assert result["status"] == EnrolmentStatus.REJECTED
    assert result["certificate_pem"] is None
    assert result["grant_public_key"] is None
