import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from cryptography.exceptions import InvalidSignature, InvalidTag
from fastapi.testclient import TestClient

from barn_compute.api_models import encode_binary
from barn_compute.coordinator.admin import create_admin_app
from barn_compute.coordinator.app import create_public_app
from barn_compute.coordinator.service import CoordinatorService
from barn_compute.crypto import (
    generate_identity,
    load_private_identity,
    load_public_key,
    public_key_bytes,
)
from barn_compute.errors import BarnError, ErrorCode
from barn_compute.grants import canonical_transfer_grant
from barn_compute.node.app import create_peer_app
from barn_compute.node.authority import PeerAuthority
from barn_compute.node.client import CoordinatorClient, PeerClient
from barn_compute.node.service import NodeService
from barn_compute.relay import create_relay_app
from barn_compute.session import SessionKeyPair, create_session_hello, verify_session_hello


def approved_nodes(tmp_path):
    coordinator = CoordinatorService(tmp_path / "coordinator")
    metadata = coordinator.initialize("LabBarn", "127.0.0.1")
    nodes = []
    for name, host in (("MacNode", "127.0.0.1"), ("WindowsNode", "127.0.0.2")):
        node = NodeService(tmp_path / name)
        node_metadata = node.initialize(name, host)
        node.pin_barn_ca(
            (coordinator.state_dir / "ca-cert.pem").read_bytes(), metadata.ca_fingerprint
        )
        invite = coordinator.create_invite(timedelta(minutes=10))
        challenge = coordinator.create_enrolment_challenge(invite.code, str(node_metadata.node_id))
        receipt = coordinator.submit_enrolment(invite.code, node.create_submission(challenge))
        node.record_receipt(receipt.request_id, receipt.receipt)
        node.complete_enrolment(coordinator.approve_enrolment(str(receipt.request_id)))
        nodes.append(node)
    return coordinator, nodes


def test_share_issues_recipient_bound_short_lived_signed_grant(tmp_path) -> None:
    coordinator, (source, recipient) = approved_nodes(tmp_path)
    now = datetime.now(UTC)
    share = coordinator.create_share(
        uuid4(),
        source.load_metadata().node_id,
        recipient.load_metadata().node_id,
        timedelta(hours=1),
        now=now,
    )

    grant = coordinator.issue_transfer_grant(
        share.share_id, recipient.load_metadata().node_id, now=now
    )
    public_key = load_public_key(
        public_key_bytes(
            load_private_identity(coordinator.state_dir / "secrets" / "grant-key.pem").public_key()
        )
    )
    public_key.verify(
        grant.signature,
        canonical_transfer_grant(
            grant.grant_id,
            grant.share_id,
            grant.transfer_id,
            grant.file_id,
            grant.source_node_id,
            grant.recipient_node_id,
            grant.issued_at,
            grant.expires_at,
        ),
    )
    assert grant.expires_at == now + timedelta(minutes=5)


def test_share_rejects_wrong_recipient_expiry_and_revocation(tmp_path) -> None:
    coordinator, (source, recipient) = approved_nodes(tmp_path)
    other = NodeService(tmp_path / "Other")
    other.initialize("Other", "127.0.0.3")
    share = coordinator.create_share(
        uuid4(),
        source.load_metadata().node_id,
        recipient.load_metadata().node_id,
        timedelta(seconds=10),
    )
    with pytest.raises(BarnError) as wrong_recipient:
        coordinator.issue_transfer_grant(share.share_id, other.load_metadata().node_id)
    assert wrong_recipient.value.code is ErrorCode.NOT_AUTHORISED

    coordinator.revoke_share(share.share_id)
    with pytest.raises(BarnError) as revoked:
        coordinator.issue_transfer_grant(share.share_id, recipient.load_metadata().node_id)
    assert revoked.value.code is ErrorCode.NOT_AUTHORISED

    expired = coordinator.create_share(
        uuid4(),
        source.load_metadata().node_id,
        recipient.load_metadata().node_id,
        timedelta(seconds=1),
        now=datetime.now(UTC) - timedelta(minutes=1),
    )
    with pytest.raises(BarnError) as expired_error:
        coordinator.issue_transfer_grant(expired.share_id, recipient.load_metadata().node_id)
    assert expired_error.value.code is ErrorCode.NOT_AUTHORISED


def test_peer_serves_only_grant_scoped_manifest_and_chunks(tmp_path) -> None:
    coordinator, (source, recipient) = approved_nodes(tmp_path)
    source_file = tmp_path / "payload.bin"
    source_file.write_bytes(b"payload")
    manifest = source.import_file(source_file)
    share = coordinator.create_share(
        manifest.file_id,
        source.load_metadata().node_id,
        recipient.load_metadata().node_id,
        timedelta(minutes=10),
    )
    grant = coordinator.issue_transfer_grant(share.share_id, recipient.load_metadata().node_id)
    grant_payload = {
        "grant_id": str(grant.grant_id),
        "share_id": str(grant.share_id),
        "transfer_id": str(grant.transfer_id),
        "file_id": str(grant.file_id),
        "source_node_id": str(grant.source_node_id),
        "recipient_node_id": str(grant.recipient_node_id),
        "issued_at": grant.issued_at.isoformat(),
        "expires_at": grant.expires_at.isoformat(),
        "signature": encode_binary(grant.signature),
    }
    header = encode_binary(json.dumps(grant_payload).encode())

    control = TestClient(create_public_app(coordinator))
    coordinator_client = CoordinatorClient(
        "https://127.0.0.1",
        source.state_dir / "barn-ca.pem",
        transport=httpx.MockTransport(
            lambda req: httpx.Response(
                (
                    response := control.request(
                        req.method, str(req.url), headers=req.headers, content=req.content
                    )
                ).status_code,
                content=response.content,
            )
        ),
    )
    client = TestClient(create_peer_app(source, PeerAuthority(source, coordinator_client)))
    target = f"/v1/files/{manifest.file_id}/manifest"
    response = client.get(
        f"/v1/files/{manifest.file_id}/manifest",
        headers={
            "X-Barn-Transfer-Grant": header,
            **CoordinatorClient._signed_headers(recipient, "GET", target, b""),
        },
    )
    assert response.status_code == 200
    assert response.json()["sha256"] == manifest.sha256
    chunk = client.get(
        f"/v1/files/{manifest.file_id}/chunks/0",
        headers={
            "X-Barn-Transfer-Grant": header,
            **CoordinatorClient._signed_headers(
                recipient, "GET", f"/v1/files/{manifest.file_id}/chunks/0", b""
            ),
        },
    )
    assert chunk.status_code == 200
    assert chunk.content == b"payload"

    wrong_file = client.get(
        f"/v1/files/{uuid4()}/chunks/0",
        headers={"X-Barn-Transfer-Grant": header},
    )
    assert wrong_file.status_code == 403


def test_recipient_journal_resumes_and_exports_without_clobbering(tmp_path) -> None:
    coordinator, (source, recipient) = approved_nodes(tmp_path)
    source_file = tmp_path / "payload.bin"
    source_file.write_bytes(b"a" * 1_048_576 + b"final")
    manifest = source.import_file(source_file)
    share = coordinator.create_share(
        manifest.file_id,
        source.load_metadata().node_id,
        recipient.load_metadata().node_id,
        timedelta(minutes=10),
    )
    grant = coordinator.issue_transfer_grant(share.share_id, recipient.load_metadata().node_id)
    first = recipient.accept_transfer_chunk(grant, manifest, 0, b"a" * 1_048_576)
    assert first.completed_chunks == (0,)
    resumed = recipient.start_transfer(grant, manifest)
    assert resumed.completed_chunks == (0,)
    recipient.accept_transfer_chunk(grant, manifest, 1, b"final")
    destination = recipient.export_transfer(grant, manifest, tmp_path / "exported.bin")
    assert destination.read_bytes() == source_file.read_bytes()
    transfer_dir = recipient.state_dir / "transfers" / str(grant.transfer_id)
    assert not (transfer_dir / "assembled.tmp").exists()
    with pytest.raises(BarnError) as error:
        recipient.export_transfer(grant, manifest, destination)
    assert error.value.code is ErrorCode.CONFIGURATION
    assert not (transfer_dir / "assembled.tmp").exists()


def test_admin_share_surface_requires_bearer_and_issues_grant(tmp_path) -> None:
    coordinator, (source, recipient) = approved_nodes(tmp_path)
    token = (coordinator.state_dir / "secrets" / "admin.token").read_text(encoding="ascii").strip()
    client = TestClient(create_admin_app(coordinator, token))
    manifest_id = uuid4()
    body = {
        "file_id": str(manifest_id),
        "source_node_id": str(source.load_metadata().node_id),
        "recipient_node_id": str(recipient.load_metadata().node_id),
        "ttl_seconds": 600,
    }
    assert client.post("/local/v1/shares", json=body).status_code == 401
    response = client.post(
        "/local/v1/shares", json=body, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    share_id = response.json()["share_id"]
    grant = client.post(
        f"/local/v1/shares/{share_id}/grant",
        params={"recipient_node_id": str(recipient.load_metadata().node_id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert grant.status_code == 200
    assert grant.json()["signature"]
    assert client.get("/local/v1/audit").status_code == 401
    audit = client.get("/local/v1/audit", headers={"Authorization": f"Bearer {token}"})
    assert audit.status_code == 200
    assert any(item["operation"] == "share.create" for item in audit.json())
    assert all(
        set(item) == {"occurred_at", "operation", "subject_id", "outcome"} for item in audit.json()
    )


def test_peer_client_orchestrates_journaled_download(tmp_path) -> None:
    coordinator, (source, recipient) = approved_nodes(tmp_path)
    source_file = tmp_path / "payload.bin"
    source_file.write_bytes(b"download me")
    manifest = source.import_file(source_file)
    share = coordinator.create_share(
        manifest.file_id,
        source.load_metadata().node_id,
        recipient.load_metadata().node_id,
        timedelta(minutes=10),
    )
    grant = coordinator.issue_transfer_grant(share.share_id, recipient.load_metadata().node_id)
    grant_payload = {
        key: (encode_binary(value) if key == "signature" else str(value))
        for key, value in grant.model_dump().items()
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/manifest"):
            return httpx.Response(200, json=manifest.model_dump(mode="json"))
        return httpx.Response(200, content=b"download me")

    transport = httpx.MockTransport(handler)
    with PeerClient("http://peer", tmp_path / "unused-ca.pem", transport=transport) as peer:
        destination = peer.download(recipient, grant_payload, tmp_path / "downloaded.bin")
    assert destination.read_bytes() == b"download me"


def admit_relay(websocket, node, payload):
    challenge = websocket.receive_json()
    proof = load_private_identity(node.state_dir / "secrets" / "identity-key.pem").sign(
        b"barn-relay-admission-v1\n"
        + payload["ticket_id"].encode()
        + b"\n"
        + str(node.load_metadata().node_id).encode()
        + b"\n"
        + challenge["nonce"].encode()
    )
    websocket.send_json(
        {
            "node_id": str(node.load_metadata().node_id),
            "ticket": payload,
            "proof": encode_binary(proof),
        }
    )


def test_relay_ticket_admission_is_signed_short_lived_and_peer_scoped(tmp_path) -> None:
    coordinator, (source, recipient) = approved_nodes(tmp_path)
    ticket = coordinator.issue_relay_ticket(
        source.load_metadata().node_id, recipient.load_metadata().node_id
    )
    payload = {
        key: (encode_binary(value) if key == "signature" else str(value))
        for key, value in ticket.model_dump().items()
    }
    public_key = public_key_bytes(
        load_private_identity(coordinator.state_dir / "secrets" / "grant-key.pem").public_key()
    )
    client = TestClient(create_relay_app(public_key))
    with client.websocket_connect("/v1/tunnel") as websocket:
        admit_relay(websocket, source, payload)
        assert websocket.receive_json()["type"] == "admitted"


def test_admin_relay_ticket_surface_and_inner_session_encryption(tmp_path) -> None:
    coordinator, (source, recipient) = approved_nodes(tmp_path)
    token = (coordinator.state_dir / "secrets" / "admin.token").read_text(encoding="ascii").strip()
    client = TestClient(create_admin_app(coordinator, token))
    response = client.post(
        "/local/v1/relay/tickets",
        params={
            "source_node_id": str(source.load_metadata().node_id),
            "recipient_node_id": str(recipient.load_metadata().node_id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["signature"]
    left, right = SessionKeyPair.generate(), SessionKeyPair.generate()
    left_cipher = left.derive(right.public_bytes(), transcript=b"ticket")
    right_cipher = right.derive(left.public_bytes(), transcript=b"ticket")
    envelope = left_cipher.seal(b"private relay payload", associated_data=b"frame-1")
    assert right_cipher.open(envelope, associated_data=b"frame-1") == b"private relay payload"
    with pytest.raises(InvalidTag):
        right_cipher.open(envelope, associated_data=b"tampered")


def test_inner_session_hello_binds_node_identity_and_ephemeral_key() -> None:
    node_id = uuid4()
    identity = generate_identity()
    session_key_pair = SessionKeyPair.generate()
    hello = create_session_hello(node_id, session_key_pair, identity, transcript=b"ticket-and-peer")
    verify_session_hello(hello, identity.public_key(), transcript=b"ticket-and-peer")
    with pytest.raises(InvalidSignature):
        verify_session_hello(hello, generate_identity().public_key(), transcript=b"ticket-and-peer")
    with pytest.raises(InvalidSignature):
        verify_session_hello(hello, identity.public_key(), transcript=b"different")


def test_renewed_grants_resume_and_repair_corrupt_chunks(tmp_path):
    coordinator, (source, recipient) = approved_nodes(tmp_path)
    path = tmp_path / "resume.bin"
    path.write_bytes(b"verified")
    manifest = source.import_file(path)
    share = coordinator.create_share(
        manifest.file_id,
        source.load_metadata().node_id,
        recipient.load_metadata().node_id,
        timedelta(minutes=10),
    )
    grant = coordinator.issue_transfer_grant(share.share_id, recipient.load_metadata().node_id)
    recipient.accept_transfer_chunk(grant, manifest, 0, b"verified")
    renewed = coordinator.issue_transfer_grant(share.share_id, recipient.load_metadata().node_id)
    assert renewed.grant_id != grant.grant_id
    assert renewed.transfer_id == grant.transfer_id
    restarted = NodeService(recipient.state_dir)
    assert restarted.start_transfer(renewed, manifest).completed_chunks == (0,)
    chunk = recipient.state_dir / "transfers" / str(grant.transfer_id) / "chunk-00000000.bin"
    chunk.write_bytes(b"corrupt!")
    assert restarted.start_transfer(renewed, manifest).completed_chunks == ()
    restarted.transfer_control(grant.transfer_id, cancelled=True)
    with pytest.raises(BarnError):
        restarted.accept_transfer_chunk(renewed, manifest, 0, b"verified")
    restarted.transfer_control(grant.transfer_id, cancelled=False)
    restarted.accept_transfer_chunk(renewed, manifest, 0, b"verified")
    assert (
        restarted.export_transfer(renewed, manifest, tmp_path / "result.bin").read_bytes()
        == b"verified"
    )


def test_export_does_not_overwrite_concurrently_created_destination(tmp_path, monkeypatch):
    import os

    coordinator, (source, recipient) = approved_nodes(tmp_path)
    path = tmp_path / "original.bin"
    path.write_bytes(b"source")
    manifest = source.import_file(path)
    share = coordinator.create_share(
        manifest.file_id,
        source.load_metadata().node_id,
        recipient.load_metadata().node_id,
        timedelta(minutes=10),
    )
    grant = coordinator.issue_transfer_grant(share.share_id, recipient.load_metadata().node_id)
    recipient.accept_transfer_chunk(grant, manifest, 0, b"source")
    destination = tmp_path / "race.bin"
    original_link = os.link

    def race(source, target):
        destination.write_bytes(b"keep me")
        original_link(source, target)

    monkeypatch.setattr(os, "link", race)
    with pytest.raises(BarnError):
        recipient.export_transfer(grant, manifest, destination)
    assert destination.read_bytes() == b"keep me"
    transfer_dir = recipient.state_dir / "transfers" / str(grant.transfer_id)
    assert not (transfer_dir / "assembled.tmp").exists()
    assert not (tmp_path / f".race.bin.{grant.transfer_id}.tmp").exists()


def test_relay_rejects_routing_outside_ticket_and_duplicate_connections(tmp_path):
    from starlette.websockets import WebSocketDisconnect

    coordinator, (source, recipient) = approved_nodes(tmp_path)
    ticket = coordinator.issue_relay_ticket(
        source.load_metadata().node_id, recipient.load_metadata().node_id
    )
    payload = {
        **ticket.model_dump(mode="json", exclude={"signature"}),
        "signature": encode_binary(ticket.signature),
    }
    key = public_key_bytes(
        load_private_identity(coordinator.state_dir / "secrets" / "grant-key.pem").public_key()
    )
    with (
        TestClient(create_relay_app(key)) as client,
        client.websocket_connect("/v1/tunnel") as left,
    ):
        admit_relay(left, source, payload)
        assert left.receive_json()["type"] == "admitted"
        with client.websocket_connect("/v1/tunnel") as duplicate:
            admit_relay(duplicate, source, payload)
            with pytest.raises(WebSocketDisconnect):
                duplicate.receive_json()
        left.send_json(
            {
                "type": "frame",
                "recipient_node_id": str(uuid4()),
                "payload": encode_binary(b"opaque"),
            }
        )
        with pytest.raises(WebSocketDisconnect):
            left.receive_json()


def test_inner_relay_envelopes_reject_replay_and_wrong_direction():
    from barn_compute.relay_transport import RelayConnection
    from barn_compute.session import SessionCipher

    sender = RelayConnection.__new__(RelayConnection)
    receiver = RelayConnection.__new__(RelayConnection)
    sender.transcript = receiver.transcript = b"ticket-and-session"
    sender.tx_sequence = receiver.rx_sequence = 0
    sender.tx = SessionCipher(b"a" * 32)
    receiver.rx = SessionCipher(b"a" * 32)
    packets = []
    sender._send = packets.append
    sender.send({"value": "private payload"})
    assert b"private payload" not in packets[0]
    receiver._receive = lambda: packets[0]
    assert receiver.receive() == {"value": "private payload"}
    with pytest.raises(InvalidTag):
        receiver.receive()
    receiver.rx_sequence = 0
    receiver.rx = SessionCipher(b"b" * 32)
    with pytest.raises(InvalidTag):
        receiver.receive()


@pytest.mark.parametrize("index", [-1, 1])
def test_source_rejects_out_of_bounds_chunks(tmp_path, index):
    coordinator, (source, recipient) = approved_nodes(tmp_path)
    path = tmp_path / "chunk.bin"
    path.write_bytes(b"chunk")
    manifest = source.import_file(path)
    share = coordinator.create_share(
        manifest.file_id,
        source.load_metadata().node_id,
        recipient.load_metadata().node_id,
        timedelta(minutes=10),
    )
    grant = coordinator.issue_transfer_grant(share.share_id, recipient.load_metadata().node_id)
    with pytest.raises(BarnError):
        source.read_grant_chunk(grant, index)


def test_relay_ticket_alone_cannot_impersonate_peer(tmp_path):
    from starlette.websockets import WebSocketDisconnect

    coordinator, (source, recipient) = approved_nodes(tmp_path)
    ticket = coordinator.issue_relay_ticket(
        source.load_metadata().node_id, recipient.load_metadata().node_id
    )
    payload = {
        **ticket.model_dump(mode="json", exclude={"signature"}),
        "signature": encode_binary(ticket.signature),
    }
    key = public_key_bytes(
        load_private_identity(coordinator.state_dir / "secrets" / "grant-key.pem").public_key()
    )
    with (
        TestClient(create_relay_app(key)) as client,
        client.websocket_connect("/v1/tunnel") as websocket,
    ):
        assert websocket.receive_json()["type"] == "challenge"
        websocket.send_json(
            {
                "node_id": str(source.load_metadata().node_id),
                "ticket": payload,
                "proof": encode_binary(b"x" * 64),
            }
        )
        with pytest.raises(WebSocketDisconnect):
            websocket.receive_json()


def test_http_body_without_content_length_is_bounded(tmp_path):
    coordinator, _ = approved_nodes(tmp_path)
    with TestClient(create_public_app(coordinator)) as client:
        response = client.post("/v1/enrolments", content=iter([b"x" * 65536, b"extra"]))
        assert response.status_code == 413


def test_managed_paths_refuse_symlink_escape(tmp_path):
    import os
    import subprocess

    _, (source, _) = approved_nodes(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (source.state_dir / "managed").symlink_to(outside, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            pytest.skip("Host does not permit creating test symlinks")
        # Directory junctions exercise Windows reparse protection without symlink privilege.
        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "New-Item -ItemType Junction -Path $env:BARN_TEST_JUNCTION "
                "-Target $env:BARN_TEST_TARGET -ErrorAction Stop | Out-Null",
            ],
            env={
                **os.environ,
                "BARN_TEST_JUNCTION": str(source.state_dir / "managed"),
                "BARN_TEST_TARGET": str(outside),
            },
            check=True,
            capture_output=True,
            timeout=15,
        )
    path = tmp_path / "payload.bin"
    path.write_bytes(b"private")
    with pytest.raises(BarnError):
        source.import_file(path)
    assert list(outside.iterdir()) == []
