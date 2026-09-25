"""Foreground Uvicorn runners for coordinator and node services."""

from __future__ import annotations

import asyncio
from pathlib import Path

import uvicorn

from .coordinator.admin import create_admin_app
from .coordinator.app import create_public_app
from .coordinator.service import CoordinatorService
from .errors import BarnError, ErrorCode
from .node.app import create_local_app, create_peer_app
from .node.service import NodeService


async def _serve(configurations: list[uvicorn.Config]) -> None:
    servers = [uvicorn.Server(configuration) for configuration in configurations]
    for server in servers:
        server.install_signal_handlers = lambda: None
    tasks = [asyncio.create_task(server.serve()) for server in servers]
    try:
        await asyncio.gather(*tasks)
    finally:
        for server in servers:
            server.should_exit = True
        await asyncio.gather(*tasks, return_exceptions=True)


def serve_coordinator(
    state_dir: Path,
    bind: str,
    port: int,
    admin_port: int,
) -> None:
    service = CoordinatorService(state_dir)
    service.load_metadata()
    token = (state_dir / "secrets" / "admin.token").read_text(encoding="ascii").strip()
    public = uvicorn.Config(
        create_public_app(service),
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
    asyncio.run(_serve([public, admin]))


def serve_node(
    state_dir: Path,
    bind: str,
    peer_port: int,
    admin_port: int,
) -> None:
    service = NodeService(state_dir)
    metadata = service.load_metadata()
    if not (state_dir / "node-cert.pem").exists():
        raise BarnError(ErrorCode.NOT_AUTHORISED, "Node must be approved before it can start")
    token = (state_dir / "secrets" / "admin.token").read_text(encoding="ascii").strip()
    peer = uvicorn.Config(
        create_peer_app(service),
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
    asyncio.run(_serve([peer, local]))

