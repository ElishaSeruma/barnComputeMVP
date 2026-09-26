import pytest
from cryptography.exceptions import InvalidTag
from typer.testing import CliRunner
from websockets.exceptions import WebSocketException

from barn_compute import __version__, cli
from barn_compute.cli import app
from barn_compute.errors import BarnError, ErrorCode

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


def test_main_returns_clean_nonzero_exit_for_barn_error(monkeypatch, capsys) -> None:
    def fail() -> None:
        raise BarnError(ErrorCode.CONFIGURATION, "safe message")

    monkeypatch.setattr(cli, "app", fail)
    with pytest.raises(SystemExit) as exited:
        cli.main()
    assert exited.value.code == 2
    assert "CONFIGURATION: safe message" in capsys.readouterr().err
    for failure in (WebSocketException("private transport details"), InvalidTag()):
        def fail_transport(failure=failure):
            raise failure

        monkeypatch.setattr(cli, "app", fail_transport)
        with pytest.raises(SystemExit) as exited:
            cli.main()
        assert exited.value.code == 2
        output = capsys.readouterr().err
        assert "CONFIGURATION" in output
        assert "private transport details" not in output
