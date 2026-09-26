"""User-facing barn command line."""

from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path
from uuid import UUID

import httpx
import typer
from cryptography.exceptions import InvalidSignature, InvalidTag
from websockets.exceptions import WebSocketException

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
from .node.client import CoordinatorClient, PeerClient
from .node.service import NodeService
from .server import serve_coordinator, serve_node, serve_relay

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
    coordinator: str = typer.Option(..., "--coordinator"),
    relay_url: str | None = typer.Option(None, "--relay-url"),
    relay_ca_cert: Path | None = typer.Option(None, "--relay-ca-cert"),
) -> None:
    serve_node(
        _node_service(state_dir).state_dir,
        bind,
        peer_port,
        admin_port,
        coordinator,
        relay_url or load_config().relay_url,
        relay_ca_cert,
    )


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
            f"{record['node_id']}  {record['name']}  {record['status']}  {record['peer_endpoint']}"
        )


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
        "overall": "ENROLLED"
        if (config.state_dir / "node" / "node-cert.pem").exists()
        else "UNREGISTERED",
    }
    if as_json:
        typer.echo(json.dumps(result, sort_keys=True))
    else:
        for key, value in result.items():
            typer.echo(f"{key}={value}")


@file_app.command("add")
def file_add(
    source: Path,
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    manifest = _node_service(state_dir).import_file(source)
    typer.echo(f"File ID: {manifest.file_id}")
    typer.echo(f"Name: {manifest.display_name}")
    typer.echo(f"Size: {manifest.size}")
    typer.echo(f"SHA-256: {manifest.sha256}")


@file_app.command("list")
def file_list(
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    for manifest in _node_service(state_dir).list_files():
        typer.echo(
            f"{manifest.file_id}  {manifest.display_name}  {manifest.size}  {manifest.sha256}"
        )


@share_app.command("create")
def share_create(
    file_id: str,
    to: str = typer.Option(..., "--to"),
    ttl: str = typer.Option("30m", "--ttl"),
    admin_url: str = typer.Option("http://127.0.0.1:8754", "--admin-url"),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
    coordinator: str | None = typer.Option(None, "--coordinator"),
) -> None:
    node = _node_service(state_dir)
    metadata = node.load_metadata()
    if coordinator is None:
        raise BarnError(ErrorCode.CONFIGURATION, "Share create requires --coordinator")
    if not any(str(item.file_id) == file_id for item in node.list_files()):
        raise BarnError(ErrorCode.INVALID_REQUEST, "File is not managed by this node")
    with CoordinatorClient(coordinator, node.state_dir / "barn-ca.pem") as client:
        share = client.signed(
            node,
            "POST",
            "/v1/shares",
            {
                "file_id": file_id,
                "source_node_id": str(metadata.node_id),
                "recipient_node_id": to,
                "ttl_seconds": int(_parse_duration(ttl).total_seconds()),
            },
        )
    typer.echo(f"Share ID: {share['share_id']}")
    typer.echo(f"Expires at: {share['expires_at']}")


@share_app.command("list")
def share_list(
    admin_url: str = typer.Option("http://127.0.0.1:8754", "--admin-url"),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
    coordinator: str | None = typer.Option(None, "--coordinator"),
) -> None:
    if coordinator:
        node = _node_service(state_dir)
        with CoordinatorClient(coordinator, node.state_dir / "barn-ca.pem") as client:
            shares = client.signed(node, "GET", "/v1/shares")
    else:
        with _admin_client(state_dir, admin_url) as client:
            shares = client.list_shares()
    for share in shares:
        typer.echo(
            f"{share['share_id']}  {share['file_id']}  {share['recipient_node_id']}  "
            f"{share['expires_at']}"
        )


@share_app.command("revoke")
def share_revoke(
    share_id: str,
    admin_url: str = typer.Option("http://127.0.0.1:8754", "--admin-url"),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
    coordinator: str | None = typer.Option(None, "--coordinator"),
) -> None:
    if coordinator:
        node = _node_service(state_dir)
        with CoordinatorClient(coordinator, node.state_dir / "barn-ca.pem") as client:
            client.signed(node, "POST", f"/v1/shares/{UUID(share_id)}/revoke")
    else:
        with _admin_client(state_dir, admin_url) as client:
            client.revoke_share(UUID(share_id))
    typer.echo(f"Revoked share {share_id}")


@share_app.command("fetch")
def share_fetch(
    share_id: str,
    source: str = typer.Option(..., "--source"),
    output: Path = typer.Option(..., "--output"),
    ca_cert: Path = typer.Option(..., "--ca-cert"),
    admin_url: str = typer.Option("http://127.0.0.1:8754", "--admin-url"),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
    coordinator: str | None = typer.Option(None, "--coordinator"),
    mode: str | None = typer.Option(None, "--mode"),
    relay_url: str | None = typer.Option(None, "--relay-url"),
    relay_ca_cert: Path | None = typer.Option(None, "--relay-ca-cert"),
) -> None:
    node = _node_service(state_dir)
    if coordinator is None:
        raise BarnError(ErrorCode.CONFIGURATION, "Share fetch requires --coordinator")
    config = load_config()
    mode = mode or config.transport_mode
    relay_url = relay_url or config.relay_url
    if mode not in ("direct", "auto", "relay") or (mode == "relay" and not relay_url):
        raise BarnError(ErrorCode.CONFIGURATION, "Invalid or unconfigured transport mode")
    with CoordinatorClient(coordinator, node.state_dir / "barn-ca.pem") as client:
        grant = client.signed(node, "POST", f"/v1/shares/{UUID(share_id)}/grant")
        try:
            if mode == "relay":
                raise ConnectionError("Relay mode requested")
            with PeerClient(source, ca_cert.expanduser().resolve()) as peer:
                destination = peer.download(node, grant, output)
            path = "direct"
        except (ConnectionError, OSError, httpx.TransportError):
            if mode == "direct" or not relay_url:
                raise BarnError(ErrorCode.CONFIGURATION, "Direct peer connection failed") from None
            from .node.authority import PeerAuthority
            from .relay_transport import RelayConnection, relay_download

            ticket = client.signed(node, "POST", f"/v1/shares/{UUID(share_id)}/relay-ticket")
            connection = RelayConnection(relay_url, node, ticket, ca=relay_ca_cert)
            destination = relay_download(connection, PeerAuthority(node, client), grant, output)
            path = "relay"
    typer.echo(f"Exported file to {destination}")
    typer.echo(f"Transport: {path}")
    from .config import write_private_json

    write_private_json(
        node.state_dir / "last-transfer.json",
        {
            "transfer_id": grant["transfer_id"],
            "transport": path,
            "exported": True,
        },
    )


@app.command("status")
def node_status(state_dir: Path | None = typer.Option(None, "--state-dir")) -> None:
    node = _node_service(state_dir)
    metadata = node.load_metadata()
    payload = {
        "node_id": str(metadata.node_id),
        "status": str(metadata.status),
        "barn_id": str(metadata.barn_id) if metadata.barn_id else None,
    }
    path = node.state_dir / "last-transfer.json"
    if path.exists():
        payload["last_transfer"] = json.loads(path.read_text(encoding="utf-8"))
    typer.echo(json.dumps(payload, sort_keys=True))


@share_app.command("inbox")
def share_inbox(
    coordinator: str = typer.Option(..., "--coordinator"),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    node = _node_service(state_dir)
    with CoordinatorClient(coordinator, node.state_dir / "barn-ca.pem") as client:
        for share in client.signed(node, "GET", "/v1/shares"):
            typer.echo(json.dumps(share, sort_keys=True))


@transfer_app.command("list")
def transfer_list(state_dir: Path | None = typer.Option(None, "--state-dir")) -> None:
    from .models import TransferJournal

    for path in sorted((_node_service(state_dir).state_dir / "transfers").glob("*/journal.json")):
        journal = TransferJournal.model_validate_json(path.read_text(encoding="utf-8"))
        typer.echo(journal.model_dump_json())


@transfer_app.command("status")
def transfer_status(
    transfer_id: str, state_dir: Path | None = typer.Option(None, "--state-dir")
) -> None:
    from .models import TransferJournal

    path = (
        _node_service(state_dir).state_dir / "transfers" / str(UUID(transfer_id)) / "journal.json"
    )
    if not path.exists():
        raise BarnError(ErrorCode.INVALID_REQUEST, "Transfer is unavailable")
    typer.echo(
        TransferJournal.model_validate_json(path.read_text(encoding="utf-8")).model_dump_json()
    )


@transfer_app.command("cancel")
def transfer_cancel(
    transfer_id: str, state_dir: Path | None = typer.Option(None, "--state-dir")
) -> None:
    _node_service(state_dir).transfer_control(UUID(transfer_id), cancelled=True)
    typer.echo(f"Cancelled transfer {transfer_id}")


@transfer_app.command("resume")
def transfer_resume(
    transfer_id: str, state_dir: Path | None = typer.Option(None, "--state-dir")
) -> None:
    _node_service(state_dir).transfer_control(UUID(transfer_id), cancelled=False)
    typer.echo("Transfer enabled; fetch the same share to resume verified chunks")


@relay_app.command("serve")
def relay_serve(
    grant_public_key: Path = typer.Option(..., "--grant-public-key"),
    cert: Path = typer.Option(..., "--cert"),
    key: Path = typer.Option(..., "--key"),
    bind: str = typer.Option("0.0.0.0", "--bind"),
    port: int = typer.Option(443, "--port", min=1, max=65535),
) -> None:
    serve_relay(grant_public_key, cert, key, bind, port)


@coordinator_app.command("grant-key-export")
def grant_key_export(
    output: Path = typer.Option(..., "--output"),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    from .crypto import load_private_identity, public_key_bytes

    service = _coordinator_service(state_dir)
    public_key = public_key_bytes(
        load_private_identity(service.state_dir / "secrets" / "grant-key.pem").public_key()
    )
    with output.open("xb") as handle:
        handle.write(public_key)
    typer.echo(f"Exported public grant key to {output}")


@coordinator_app.command("audit")
def coordinator_audit(
    admin_url: str = typer.Option("http://127.0.0.1:8754", "--admin-url"),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    with _admin_client(state_dir, admin_url) as client:
        for event in client._payload(client._request("GET", "/local/v1/audit")):
            typer.echo(json.dumps(event, sort_keys=True))


@node_app.command("revoke")
def node_revoke(
    node_id: str,
    admin_url: str = typer.Option("http://127.0.0.1:8754", "--admin-url"),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
) -> None:
    with _admin_client(state_dir, admin_url) as client:
        client._payload(client._request("POST", f"/local/v1/nodes/{UUID(node_id)}/revoke"))
    typer.echo(f"Revoked node {node_id}")


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
            f"{record['node_id']}  {record['name']}  {record['status']}  {record['peer_endpoint']}"
        )


def main() -> None:
    try:
        app()
    except BarnError as exc:
        typer.echo(f"{exc.code}: {exc.message}", err=True)
        raise SystemExit(2) from None
    except (OSError, ValueError, httpx.HTTPError, WebSocketException, InvalidSignature, InvalidTag):
        typer.echo(
            "CONFIGURATION: Operation failed; check paths, network and trusted certificates",
            err=True,
        )
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
