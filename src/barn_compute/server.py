"""Foreground Uvicorn runners for coordinator and node services."""

from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import uvicorn

from .coordinator.admin import create_admin_app
from .coordinator.app import create_public_app
from .coordinator.service import CoordinatorService
from .errors import BarnError, ErrorCode
from .node.app import create_local_app, create_peer_app
from .node.authority import PeerAuthority
from .node.client import CoordinatorClient
from .node.service import NodeService


async def _serve(configurations: list[uvicorn.Config]) -> None:
    servers = [uvicorn.Server(configuration) for configuration in configurations]
    for server in servers:
        server.install_signal_handlers = lambda: None
    tasks = [asyncio.create_task(server.serve()) for server in servers]
    try:
        finished, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in finished:
            task.result()
    finally:
        for server in servers:
            server.should_exit = True
        await asyncio.gather(*tasks, return_exceptions=True)


def serve_coordinator(
    state_dir: Path,
    bind: str,
    port: int,
    admin_port: int,
    relay_url: str | None = None,
    relay_ca: Path | None = None,
) -> None:
    service = CoordinatorService(state_dir)
    service.load_metadata()
    token = (state_dir / "secrets" / "admin.token").read_text(encoding="ascii").strip()
    public_app = create_public_app(service)
    public = uvicorn.Config(
        public_app,
        host=bind,
        port=port,
        ssl_certfile=str(state_dir / "coordinator-cert.pem"),
        ssl_keyfile=str(state_dir / "secrets" / "coordinator-key.pem"),
        log_level="info",
    )
    admin = uvicorn.Config(
        create_admin_app(service, token),
        host="127.0.0.1",
        port=admin_port,
        log_level="warning",
    )
    stop = threading.Event()
    control = None
    if relay_url:
        from .control_transport import run_coordinator_control

        control = threading.Thread(
            target=run_coordinator_control,
            args=(service, public_app, relay_url, relay_ca, stop),
            daemon=True,
        )
        control.start()
    try:
        asyncio.run(_serve([public, admin]))
    finally:
        stop.set()
        if control is not None:
            control.join(timeout=20)


def serve_node(
    state_dir: Path,
    bind: str,
    peer_port: int,
    admin_port: int,
    coordinator_url: str | None = None,
    relay_url: str | None = None,
    relay_ca: Path | None = None,
) -> None:
    service = NodeService(state_dir)
    metadata = service.load_metadata()
    if not (state_dir / "node-cert.pem").exists():
        raise BarnError(ErrorCode.NOT_AUTHORISED, "Node must be approved before it can start")
    token = (state_dir / "secrets" / "admin.token").read_text(encoding="ascii").strip()
    if coordinator_url is None:
        raise BarnError(ErrorCode.CONFIGURATION, "Node start requires --coordinator for authority")
    client = CoordinatorClient(
        coordinator_url,
        state_dir / "barn-ca.pem",
        relay_url=relay_url,
        relay_ca=relay_ca,
    )
    authority = PeerAuthority(service, client)
    peer = uvicorn.Config(
        create_peer_app(service, authority),
        host=bind,
        port=peer_port or metadata.peer_port,
        ssl_certfile=str(state_dir / "node-cert.pem"),
        ssl_keyfile=str(state_dir / "secrets" / "tls-key.pem"),
        log_level="info",
    )
    local = uvicorn.Config(
        create_local_app(service, token),
        host="127.0.0.1",
        port=admin_port,
        log_level="warning",
    )
    stop = threading.Event()
    agent = threading.Thread(
        target=run_agent,
        args=(service, coordinator_url, stop),
        kwargs={"relay_url": relay_url, "relay_ca": relay_ca},
        daemon=True,
    )
    agent.start()
    try:
        asyncio.run(_serve([peer, local]))
    finally:
        stop.set()
        agent.join(timeout=20)
        client.close()


def run_agent(
    node: NodeService,
    coordinator_url: str,
    stop: threading.Event,
    *,
    relay_url: str | None = None,
    relay_ca: Path | None = None,
) -> None:
    from .relay_transport import RelayConnection, serve_relay_transfer

    log = logging.getLogger(__name__)
    active = {}
    completed = set()

    def transfer(ticket: dict) -> None:
        with CoordinatorClient(
            coordinator_url,
            node.state_dir / "barn-ca.pem",
            relay_url=relay_url,
            relay_ca=relay_ca,
        ) as client:
            connection = RelayConnection(relay_url, node, ticket, ca=relay_ca)
            serve_relay_transfer(connection, PeerAuthority(node, client))

    with (
        ThreadPoolExecutor(max_workers=8) as pool,
        CoordinatorClient(
            coordinator_url,
            node.state_dir / "barn-ca.pem",
            relay_url=relay_url,
            relay_ca=relay_ca,
        ) as client,
    ):
        if relay_url:
            try:
                client.refresh_control_grant(node)
            except Exception:
                log.warning("Control grant refresh failed; using any retained valid grant")
        heartbeat_at = 0
        import time

        while not stop.is_set():
            try:
                if time.monotonic() >= heartbeat_at:
                    client.send_heartbeat(node)
                    client.refresh_registry(node)
                    heartbeat_at = time.monotonic() + 15
                for ticket_id, future in list(active.items()):
                    if future.done():
                        if future.exception() is not None:
                            log.warning("Relay session failed; recipient may retry")
                        completed.add(ticket_id)
                        del active[ticket_id]
                if relay_url:
                    tickets = client.signed(node, "GET", "/v1/relay/tickets")
                    live = {ticket["ticket_id"] for ticket in tickets}
                    completed.intersection_update(live)
                    for ticket in tickets:
                        ticket_id = ticket["ticket_id"]
                        if (
                            ticket_id not in active
                            and ticket_id not in completed
                            and len(active) < 8
                        ):
                            active[ticket_id] = pool.submit(transfer, ticket)
            except Exception:
                log.warning("Coordinator connection failed; retrying with verified TLS")
            stop.wait(1)


def serve_relay(grant_public_key: Path, certificate: Path, key: Path, bind: str, port: int) -> None:
    from .relay import create_relay_app

    uvicorn.run(
        create_relay_app(grant_public_key.read_bytes()),
        host=bind,
        port=port,
        ssl_certfile=str(certificate),
        ssl_keyfile=str(key),
        ws_max_size=2 * 1024 * 1024,
        ws_max_queue=4,
        log_level="warning",
        access_log=False,
    )
