"""Real TLS/WSS transfer acceptance with isolated disposable nodes."""

import hashlib
import socket
import threading
import time
from contextlib import ExitStack, contextmanager
from datetime import timedelta

import httpx
import pytest
import uvicorn

from barn_compute.coordinator.admin import create_admin_app
from barn_compute.coordinator.app import create_public_app
from barn_compute.coordinator.service import CoordinatorService
from barn_compute.crypto import load_private_identity, public_key_bytes
from barn_compute.errors import BarnError
from barn_compute.node.app import create_peer_app
from barn_compute.node.authority import PeerAuthority
from barn_compute.node.client import CoordinatorClient, PeerClient
from barn_compute.node.service import NodeService
from barn_compute.relay import create_relay_app
from barn_compute.relay_transport import RelayConnection, relay_download
from barn_compute.server import run_agent


@contextmanager
def live_server(app, certificate=None, key=None):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            log_level="error",
            access_log=False,
            lifespan="off",
            ssl_certfile=str(certificate) if certificate else None,
            ssl_keyfile=str(key) if key else None,
            ws_max_size=2 * 1024 * 1024,
            ws_max_queue=4,
        )
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("Test service failed to start")
            time.sleep(0.01)
        yield f"{'https' if certificate else 'http'}://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(10)
        listener.close()
        assert not thread.is_alive(), "Test server failed to stop"


@pytest.fixture
def network(tmp_path):
    coordinator = CoordinatorService(tmp_path / "coordinator")
    meta = coordinator.initialize("NetworkBarn", "127.0.0.1")
    nodes = []
    for name in ("Mac", "Windows"):
        node = NodeService(tmp_path / name)
        node.initialize(name, "127.0.0.1")
        node.pin_barn_ca((coordinator.state_dir / "ca-cert.pem").read_bytes(), meta.ca_fingerprint)
        invite = coordinator.create_invite(timedelta(minutes=10))
        challenge = coordinator.create_enrolment_challenge(
            invite.code, str(node.load_metadata().node_id)
        )
        receipt = coordinator.submit_enrolment(invite.code, node.create_submission(challenge))
        node.record_receipt(receipt.request_id, receipt.receipt)
        node.complete_enrolment(coordinator.approve_enrolment(str(receipt.request_id)))
        nodes.append(node)
    with ExitStack() as stack:
        url = stack.enter_context(
            live_server(
                create_public_app(coordinator),
                coordinator.state_dir / "coordinator-cert.pem",
                coordinator.state_dir / "secrets" / "coordinator-key.pem",
            )
        )
        clients = [
            stack.enter_context(CoordinatorClient(url, node.state_dir / "barn-ca.pem"))
            for node in nodes
        ]
        authorities = [
            PeerAuthority(node, client) for node, client in zip(nodes, clients, strict=True)
        ]
        peers = [
            stack.enter_context(
                live_server(
                    create_peer_app(node, authority),
                    node.state_dir / "node-cert.pem",
                    node.state_dir / "secrets" / "tls-key.pem",
                )
            )
            for node, authority in zip(nodes, authorities, strict=True)
        ]
        public_key = public_key_bytes(
            load_private_identity(coordinator.state_dir / "secrets" / "grant-key.pem").public_key()
        )
        relay = (
            stack.enter_context(
                live_server(
                    create_relay_app(public_key),
                    coordinator.state_dir / "coordinator-cert.pem",
                    coordinator.state_dir / "secrets" / "coordinator-key.pem",
                )
            ).replace("https://", "wss://")
            + "/v1/tunnel"
        )
        stop = threading.Event()
        threads = [
            threading.Thread(
                target=run_agent,
                args=(node, url, stop),
                kwargs={
                    "relay_url": relay,
                    "relay_ca": coordinator.state_dir / "ca-cert.pem",
                },
                daemon=True,
            )
            for node in nodes
        ]
        for thread in threads:
            thread.start()
        try:
            yield coordinator, nodes, clients, authorities, peers, relay
        finally:
            stop.set()
            for thread in threads:
                thread.join(20)
                assert not thread.is_alive(), "Agent failed to stop"


def share(client, node, recipient, manifest):
    value = client.signed(
        node,
        "POST",
        "/v1/shares",
        {
            "file_id": str(manifest.file_id),
            "source_node_id": str(node.load_metadata().node_id),
            "recipient_node_id": str(recipient.load_metadata().node_id),
            "ttl_seconds": 600,
        },
    )
    return value["share_id"]


@pytest.mark.parametrize("size", [0, 1, 1024 * 1024, 1024 * 1024 + 1])
def test_direct_boundaries_and_signed_recipient(network, tmp_path, size):
    coordinator, nodes, clients, _, peers, _ = network
    source, recipient = nodes
    path = tmp_path / "boundary.bin"
    path.write_bytes(b"x" * size)
    manifest = source.import_file(path)
    share_id = share(clients[0], source, recipient, manifest)
    grant = clients[1].signed(recipient, "POST", f"/v1/shares/{share_id}/grant")
    with PeerClient(peers[0], recipient.state_dir / "barn-ca.pem") as peer:
        destination = peer.download(recipient, grant, tmp_path / "result.bin")
        target = f"/v1/files/{manifest.file_id}/manifest"
        assert (
            peer.client.get(
                target, headers={"X-Barn-Transfer-Grant": PeerClient._grant_header(grant)}
            ).status_code
            == 403
        )
        headers = {
            "X-Barn-Transfer-Grant": PeerClient._grant_header(grant),
            **CoordinatorClient._signed_headers(recipient, "GET", target, b""),
        }
        assert peer.client.get(target, headers=headers).status_code == 200
        assert peer.client.get(target, headers=headers).status_code == 409
        clients[0].signed(source, "POST", f"/v1/shares/{share_id}/revoke")
        assert (
            peer.client.get(
                target,
                headers={
                    "X-Barn-Transfer-Grant": PeerClient._grant_header(grant),
                    **CoordinatorClient._signed_headers(recipient, "GET", target, b""),
                },
            ).status_code
            == 403
        )
    assert destination.read_bytes() == path.read_bytes()


def test_relay_both_directions_and_resume(network, tmp_path):
    coordinator, nodes, clients, authorities, _, relay = network
    for index in (0, 1):
        source, recipient = nodes[index], nodes[1 - index]
        path = tmp_path / f"relay-{index}.bin"
        # Deterministic 100 MiB acceptance fixture, written without one large allocation.
        block = hashlib.sha256(b"barnCompute-M1").digest() * (1024 * 1024 // 32)
        with path.open("wb") as output:
            for _ in range(100):
                output.write(block)
        manifest = source.import_file(path)
        direct_share_id = share(clients[index], source, recipient, manifest)
        direct_grant = clients[1 - index].signed(
            recipient, "POST", f"/v1/shares/{direct_share_id}/grant"
        )
        with PeerClient(network[4][index], recipient.state_dir / "barn-ca.pem") as peer:
            direct_destination = peer.download(
                recipient, direct_grant, tmp_path / f"direct-{index}.bin"
            )
        with direct_destination.open("rb") as result:
            assert hashlib.file_digest(result, "sha256").hexdigest() == manifest.sha256
        share_id = share(clients[index], source, recipient, manifest)
        client = clients[1 - index]
        grant = client.signed(recipient, "POST", f"/v1/shares/{share_id}/grant")
        from barn_compute.api_models import decode_binary
        from barn_compute.models import TransferGrant

        model = TransferGrant.model_validate(
            {**grant, "signature": decode_binary(grant["signature"])}
        )
        recipient.accept_transfer_chunk(model, manifest, 0, block)
        renewed = client.signed(recipient, "POST", f"/v1/shares/{share_id}/grant")
        assert renewed["transfer_id"] == grant["transfer_id"]
        ticket = client.signed(recipient, "POST", f"/v1/shares/{share_id}/relay-ticket")
        connection = RelayConnection(
            relay, recipient, ticket, ca=coordinator.state_dir / "ca-cert.pem"
        )
        destination = relay_download(
            connection, authorities[1 - index], renewed, tmp_path / f"out-{index}.bin"
        )
        with destination.open("rb") as result:
            assert hashlib.file_digest(result, "sha256").hexdigest() == manifest.sha256
        assert any(item.sha256 == manifest.sha256 for item in recipient.list_files())


def test_tls_rejects_unknown_ca(network, tmp_path):
    _, nodes, _, _, peers, _ = network
    unknown = CoordinatorService(tmp_path / "unknown")
    unknown.initialize("OtherBarn", "127.0.0.1")
    with (
        PeerClient(peers[0], unknown.state_dir / "ca-cert.pem") as peer,
        pytest.raises(httpx.ConnectError),
    ):
        peer.client.get("/v1/health")


def test_cli_auto_falls_back_to_live_relay(network, tmp_path, capsys):
    from barn_compute.cli import share_fetch

    coordinator, nodes, clients, _, _, relay = network
    source, recipient = nodes
    path = tmp_path / "fallback.bin"
    path.write_bytes(b"automatic fallback")
    manifest = source.import_file(path)
    share_id = share(clients[0], source, recipient, manifest)
    # Bind an unused port, with no listening socket, for a deterministic direct failure.
    with socket.socket() as closed:
        closed.bind(("127.0.0.1", 0))
        direct_url = f"https://127.0.0.1:{closed.getsockname()[1]}"
        share_fetch(
            share_id,
            source=direct_url,
            output=tmp_path / "fallback-result.bin",
            ca_cert=recipient.state_dir / "barn-ca.pem",
            admin_url="unused",
            state_dir=recipient.state_dir,
            coordinator=str(clients[0].client.base_url),
            mode="auto",
            relay_url=relay,
            relay_ca_cert=coordinator.state_dir / "ca-cert.pem",
        )
    assert (tmp_path / "fallback-result.bin").read_bytes() == b"automatic fallback"
    assert "Transport: relay" in capsys.readouterr().out


def test_revoked_node_cannot_get_grant_or_identity(network):
    coordinator, nodes, clients, _, _, _ = network
    token = (coordinator.state_dir / "secrets" / "admin.token").read_text().strip()
    from fastapi.testclient import TestClient

    with TestClient(create_admin_app(coordinator, token)) as admin:
        assert (
            admin.post(
                f"/local/v1/nodes/{nodes[1].load_metadata().node_id}/revoke",
                headers={"Authorization": f"Bearer {token}"},
            ).status_code
            == 204
        )
    with pytest.raises(BarnError):
        clients[1].signed(nodes[1], "GET", "/v1/shares")
