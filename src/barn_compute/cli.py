"""User-facing barn command line."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from . import __version__
from .config import (
    BarnConfig,
    default_config_path,
    ensure_private_directory,
    load_config,
    save_config,
)
from .errors import BarnError, ErrorCode

app = typer.Typer(help="Private authenticated device groups and secure file exchange.")
config_app = typer.Typer(help="Manage local barnCompute configuration.")
coordinator_app = typer.Typer(help="Create and administer a Barn coordinator.")
node_app = typer.Typer(help="Create, enrol, and run a node agent.")
file_app = typer.Typer(help="Import and list managed files.")
share_app = typer.Typer(help="Create and fetch explicit file shares.")
transfer_app = typer.Typer(help="Inspect and control transfers.")
relay_app = typer.Typer(help="Run and configure the optional relay service.")

app.add_typer(config_app, name="config")
app.add_typer(coordinator_app, name="coordinator")
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
    del name, advertise
    path = ensure_private_directory(state_dir or load_config().state_dir / "coordinator")
    typer.echo(f"Coordinator state directory prepared at {path}")
    typer.echo("Identity and CA creation are the next implementation stage.")


for command_name, command_help in (
    ("start", "Start the coordinator services."),
    ("invite", "Create a one-use enrolment invitation."),
    ("enrolments", "List pending enrolment requests."),
    ("approve", "Approve a pending enrolment request."),
):
    coordinator_app.command(command_name, help=command_help)(
        _pending_command(f"coordinator {command_name}")
    )


@node_app.command("init")
def node_init(
    name: str = typer.Option(..., "--name"),
    advertise: str = typer.Option(..., "--advertise"),
    peer_port: int = typer.Option(8445, "--peer-port", min=1, max=65535),
) -> None:
    del name, advertise, peer_port
    _pending("node init")


for command_name in ("enroll", "start", "revoke"):
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
def nodes() -> None:
    _pending("nodes")


def main() -> None:
    try:
        app()
    except BarnError as exc:
        typer.echo(f"{exc.code}: {exc.message}", err=True)
        raise typer.Exit(code=2) from exc


if __name__ == "__main__":
    main()
