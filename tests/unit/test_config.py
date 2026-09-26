import json
import os

import pytest
from pydantic import ValidationError

from barn_compute.config import BarnConfig, load_config, save_config
from barn_compute.errors import BarnError


def test_config_round_trip(tmp_path) -> None:
    path = tmp_path / "config" / "config.json"
    config = BarnConfig(
        state_dir=tmp_path / "state",
        transport_mode="relay",
        relay_url="wss://relay.example.test/v1/tunnel",
    )
    assert save_config(config, path) == path
    assert load_config(path) == config
    assert json.loads(path.read_text())["transport_mode"] == "relay"
    if os.name != "nt":
        assert path.stat().st_mode & 0o077 == 0


def test_transport_mode_is_validated(tmp_path) -> None:
    with pytest.raises(ValidationError):
        BarnConfig(state_dir=tmp_path, transport_mode="plaintext")
    malformed = BarnConfig.model_construct(
        state_dir=tmp_path, relay_url="wss://private-user:private-password@relay.example/v1/tunnel"
    )
    path = tmp_path / "invalid-config.json"
    save_config(malformed, path)
    with pytest.raises(BarnError) as failure:
        load_config(path)
    assert "private-user" not in failure.value.message
    assert "private-password" not in failure.value.message
