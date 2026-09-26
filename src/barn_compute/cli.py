"""User-facing barn command line."""

from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path

import typer

from . import __version__
from .config import (
    BarnConfig,
    default_config_path,
    load_config,
    save_config,
)
from .coordinator.admin_client import CoordinatorAdminClient
from .coordinator.service import CoordinatorService
from .errors import BarnError, ErrorCode
from .node.client import CoordinatorClient
from .node.service import NodeService
from .server import serve_coordinator, serve_node

app = typer.Typer(help="Private authenticated device groups and secure file exchange.")
config_app = typer.Typer(help="Manage local barnCompute configuration.")
coordinator_app = typer.Typer(help="Create and administer a Barn coordinator.")
coordinator_ca_app = typer.Typer(help="Export and inspect the Barn public CA.")
node_app = typer.Typer(help="Create, enrol, and run a node agent.")
file_app = typer.Typer(help="Import and list managed files.")
share_app = typer.Typer(help="Create and fetch explicit file shares.")
transfer_app = typer.Typer(help="Inspect and control transfers.")
relay_app = typer.Typer(help="Run and configure the optional relay service.")

app.add_typer(config_app, name="config")
app.add_typer(coordinator_app, name="coordinator")
coordinator_app.add_typer(coordinator_ca_app, name="ca")
app.add_typer(node_app, name="node")
app.add_typer(file_app, name="file")
app.add_typer(share_app, name="share")
app.add_typer(transfer_app, name="transfer")
app.add_typer(relay_app, name="relay")


def _version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def root(
    version: bool = typer.Option(False, "--version", callback=_version, is_eager=True),
) -> None:
    """Run barnCompute commands."""


def _pending(feature: str) -> None:
    raise BarnError(ErrorCode.NOT_IMPLEMENTED, f"{feature} is not implemented in this build")


def _pending_command(feature: str):
    def command() -> None:
        _pending(feature)

    command.__name__ = feature.replace(" ", "_")
    return command


def _coordinator_service(state_dir: Path | None) -> CoordinatorService:
    path = state_dir or load_config().state_dir / "coordinator"
    return CoordinatorService(path)


def _node_service(state_dir: Path | None) -> NodeService:
    path = state_dir or load_config().state_dir / "node"
    return NodeService(path)


def _admin_client(state_dir: Path | None, admin_url: str) -> CoordinatorAdminClient:
    return CoordinatorAdminClient(_coordinator_service(state_dir).state_dir, admin_url)


def _parse_duration(value: str) -> timedelta:
    match = re.fullmatch(r"([1-9][0-9]*)([smh])", value.strip().lower())
    if match is None:
        raise BarnError(ErrorCode.INVALID_REQUEST, "Duration must look like 10m, 30s, or 1h")
    amount = int(match.group(1))
    unit = match.group(2)
    seconds = amount * {"s": 1, "m": 60, "h": 3600}[unit]
    return timedelta(seconds=seconds)


@config_app.command("show")
def config_show(as_json: bool = typer.Option(False, "--json")) -> None:
    config = load_config()
    payload = config.model_dump(mode="json")
    if as_json:
        typer.echo(json.dumps(payload, sort_keys=True))
    else:
        typer.echo(f"state_dir={payload['state_dir']}")
        typer.echo(f"transport.mode={payload['transport_mode']}")
        typer.echo(f"relay.url={payload['relay_url'] or '<not configured>'}")


@config_app.command("set")
def config_set(key: str, value: str) -> None:
    config = load_config()
    if key == "transport.mode":
        config = config.model_copy(update={"transport_mode": value})
    elif key == "relay.url":
        if not value.startswith("wss://"):
            raise BarnError(ErrorCode.CONFIGURATION, "relay.url must use wss://")
        config = config.model_copy(update={"relay_url": value})
    else:
        raise BarnError(ErrorCode.CONFIGURATION, f"Unknown configuration key: {key}")
    config = BarnConfig.model_validate(config.model_dump())
    path = save_config(config)
    typer.echo(f"Updated {key} in {path}")


@coordinator_app.command("init")
def coordinator_init(
    name: str = typer.Option(..., "--name"),
    advertise: str = typer.Option(..., "--advertise"),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    metadata = _coordinator_service(state_dir).initialize(name, advertise)
    typer.echo(f"Barn ID: {metadata.barn_id}")
    typer.echo(f"CA SHA-256: {metadata.ca_fingerprint}")
    typer.echo("Coordinator initialized. Keep its state directory private and backed up.")


@coordinator_ca_app.command("export")
def coordinator_ca_export(
    output: Path = typer.Option(..., "--output"),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    fingerprint = _coordinator_service(state_dir).export_ca(output.expanduser().resolve())
    typer.echo(f"Exported public Barn CA to {output}")
    typer.echo(f"CA SHA-256: {fingerprint}")


@coordinator_app.command("invite")
def coordinator_invite(
    ttl: str = typer.Option("10m", "--ttl"),
    admin_url: str = typer.Option("http://127.0.0.1:8754", "--admin-url"),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    with _admin_client(state_dir, admin_url) as client:
        invite = client.create_invite(_parse_duration(ttl))
    typer.echo(f"Invite ID: {invite['invite_id']}")
    typer.echo(f"One-use code: {invite['code']}")
    typer.echo(f"Expires at: {invite['expires_at']}")
    typer.echo("Convey this code privately. It will not be displayed again.")


@coordinator_app.command("enrolments")
def coordinator_enrolments(
    admin_url: str = typer.Option("http://127.0.0.1:8754", "--admin-url"),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    with _admin_client(state_dir, admin_url) as client:
        pending = client.list_enrolments()
    if not pending:
        typer.echo("No pending enrolments.")
        return
    for request in pending:
        typer.echo(
            f"{request['request_id']}  {request['node_name']}  {request['node_id']}  "
            f"{request['advertised_host']}:{request['peer_port']}  "
            f"fingerprint={request['identity_fingerprint']}"
        )


@coordinator_app.command("approve")
def coordinator_approve(
    request_id: str,
    admin_url: str = typer.Option("http://127.0.0.1:8754", "--admin-url"),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    with _admin_client(state_dir, admin_url) as client:
        result = client.approve(request_id)
    typer.echo(f"Approved enrolment {result['request_id']}")


@coordinator_app.command("reject")
def coordinator_reject(
    request_id: str,
    admin_url: str = typer.Option("http://127.0.0.1:8754", "--admin-url"),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    with _admin_client(state_dir, admin_url) as client:
        client.reject(request_id)
    typer.echo(f"Rejected enrolment {request_id}")


@coordinator_app.command("start")
def coordinator_start(
    bind: str = typer.Option("0.0.0.0", "--bind"),
    port: int = typer.Option(8443, "--port", min=1, max=65535),
    admin_port: int = typer.Option(8754, "--admin-port", min=1, max=65535),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    serve_coordinator(_coordinator_service(state_dir).state_dir, bind, port, admin_port)


@node_app.command("init")
def node_init(
    name: str = typer.Option(..., "--name"),
    advertise: str = typer.Option(..., "--advertise"),
    peer_port: int = typer.Option(8445, "--peer-port", min=1, max=65535),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    metadata = _node_service(state_dir).initialize(name, advertise, peer_port)
    typer.echo(f"Node ID: {metadata.node_id}")
    typer.echo(f"Identity SHA-256: {metadata.identity_fingerprint}")
    typer.echo("Node initialized. Enrol it with the coordinator over verified HTTPS.")


@node_app.command("enroll")
def node_enroll(
    coordinator: str = typer.Option(..., "--coordinator"),
    ca_cert: Path = typer.Option(..., "--ca-cert"),
    ca_fingerprint: str = typer.Option(..., "--ca-fingerprint"),
    code: str | None = typer.Option(None, "--code", help="Omit to enter it privately."),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    node = _node_service(state_dir)
    certificate = ca_cert.expanduser().resolve().read_bytes()
    node.pin_barn_ca(certificate, ca_fingerprint)
    invite_code = code or typer.prompt("One-use invitation code", hide_input=True)
    with CoordinatorClient(coordinator, ca_cert.expanduser().resolve()) as client:
        receipt = client.submit_enrolment(node, invite_code)
    typer.echo(f"Enrolment request: {receipt.request_id}")
    typer.echo("Status: AWAITING_APPROVAL")


@node_app.command("enrolment-status")
def node_enrolment_status(
    coordinator: str = typer.Option(..., "--coordinator"),
    ca_cert: Path = typer.Option(..., "--ca-cert"),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    node = _node_service(state_dir)
    with CoordinatorClient(coordinator, ca_cert.expanduser().resolve()) as client:
        result = client.poll_enrolment(node)
    typer.echo(f"Status: {result.status}")


@node_app.command("start")
def node_start(
    bind: str = typer.Option("0.0.0.0", "--bind"),
    peer_port: int = typer.Option(8445, "--peer-port", min=1, max=65535),
    admin_port: int = typer.Option(8755, "--admin-port", min=1, max=65535),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    serve_node(_node_service(state_dir).state_dir, bind, peer_port, admin_port)


@node_app.command("heartbeat")
def node_heartbeat(
    coordinator: str = typer.Option(..., "--coordinator"),
    ca_cert: Path = typer.Option(..., "--ca-cert"),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    node = _node_service(state_dir)
    with CoordinatorClient(coordinator, ca_cert.expanduser().resolve()) as client:
        result = client.send_heartbeat(node)
    typer.echo(f"Status: {result['status']}")


@node_app.command("registry-refresh")
def node_registry_refresh(
    coordinator: str = typer.Option(..., "--coordinator"),
    ca_cert: Path = typer.Option(..., "--ca-cert"),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    node = _node_service(state_dir)
    with CoordinatorClient(coordinator, ca_cert.expanduser().resolve()) as client:
        result = client.refresh_registry(node)
    for record in result["nodes"]:
        typer.echo(
            f"{record['node_id']}  {record['name']}  {record['status']}  "
            f"{record['peer_endpoint']}"
        )


for command_name in ("revoke",):
    node_app.command(command_name)(_pending_command(f"node {command_name}"))


for child_app, names in (
    (file_app, ("add", "list")),
    (share_app, ("create", "inbox", "list", "fetch", "revoke")),
    (transfer_app, ("list", "status", "resume", "cancel")),
    (relay_app, ("serve",)),
):
    for command_name in names:
        child_app.command(command_name)(_pending_command(command_name))


@app.command("doctor")
def doctor(as_json: bool = typer.Option(False, "--json")) -> None:
    config = load_config()
    state_exists = config.state_dir.exists()
    result = {
        "version": __version__,
        "config_path": str(default_config_path()),
        "state_dir": str(config.state_dir),
        "state_dir_exists": state_exists,
        "transport_mode": config.transport_mode,
        "relay_configured": config.relay_url is not None,
        "overall": "INCOMPLETE",
    }
    if as_json:
        typer.echo(json.dumps(result, sort_keys=True))
    else:
        for key, value in result.items():
            typer.echo(f"{key}={value}")


@app.command("nodes")
def nodes(
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    path = _node_service(state_dir).state_dir / "registry.json"
    if not path.exists():
        raise BarnError(ErrorCode.CONFIGURATION, "Registry is unavailable; refresh it first")
    payload = json.loads(path.read_text(encoding="utf-8"))
    for record in payload["nodes"]:
        typer.echo(
            f"{record['node_id']}  {record['name']}  {record['status']}  "
            f"{record['peer_endpoint']}"
        )


def main() -> None:
    try:
        app()
    except BarnError as exc:
        typer.echo(f"{exc.code}: {exc.message}", err=True)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
