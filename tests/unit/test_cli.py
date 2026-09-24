from typer.testing import CliRunner

from barn_compute import __version__
from barn_compute.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_help_lists_primary_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("coordinator", "node", "file", "share", "transfer", "relay", "doctor"):
        assert command in result.stdout

