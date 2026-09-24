"""Typed errors shared by the CLI and protocol layers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ErrorCode(StrEnum):
    CONFIGURATION = "CONFIGURATION"
    INVALID_REQUEST = "INVALID_REQUEST"
    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    NOT_AUTHORISED = "NOT_AUTHORISED"
    REPLAY_DETECTED = "REPLAY_DETECTED"
    CLOCK_SKEW = "CLOCK_SKEW"
    PROTOCOL_MISMATCH = "PROTOCOL_MISMATCH"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


@dataclass(slots=True)
class BarnError(Exception):
    code: ErrorCode
    message: str

    def __str__(self) -> str:
        return self.message

    def as_dict(self) -> dict[str, dict[str, str]]:
        return {"error": {"code": self.code, "message": self.message}}

