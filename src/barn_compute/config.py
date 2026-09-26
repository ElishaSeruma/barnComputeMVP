"""Platform-aware configuration and private state directories."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from platformdirs import user_config_path, user_data_path
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .errors import BarnError, ErrorCode


class BarnConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_dir: Path
    transport_mode: str = Field(default="auto", pattern="^(auto|direct|relay)$")
    relay_url: str | None = None

    @field_validator("relay_url")
    @classmethod
    def require_safe_relay(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlsplit(value)
        if parsed.scheme != "wss" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Relay URL must use WSS without credentials")
        if parsed.query or parsed.fragment:
            raise ValueError("Relay URL must not contain query parameters or a fragment")
        return value


def default_state_dir() -> Path:
    return user_data_path("barnCompute", "barnCompute")


def default_config_path() -> Path:
    return user_config_path("barnCompute", "barnCompute") / "config.json"


def ensure_private_directory(path: Path) -> Path:
    path = path.expanduser().resolve()
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != "nt":
        path.chmod(stat.S_IRWXU)
    return path


def write_private_json(path: Path, payload: dict[str, Any]) -> None:
    write_private_bytes(path, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode())


def write_private_bytes(path: Path, data: bytes) -> None:
    ensure_private_directory(path.parent)
    temporary = path.with_suffix(path.suffix + ".tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    finally:
        temporary.unlink(missing_ok=True)


def load_config(path: Path | None = None) -> BarnConfig:
    config_path = path or default_config_path()
    if not config_path.exists():
        return BarnConfig(state_dir=default_state_dir())
    try:
        return BarnConfig.model_validate_json(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BarnError(ErrorCode.CONFIGURATION, f"Invalid config at {config_path}") from exc


def save_config(config: BarnConfig, path: Path | None = None) -> Path:
    config_path = path or default_config_path()
    write_private_json(config_path, config.model_dump(mode="json"))
    return config_path
