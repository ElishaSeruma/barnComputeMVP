"""Fail-closed transport selection and direct-to-relay policy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

import httpx

from .errors import BarnError, ErrorCode

T = TypeVar("T")


class TransportPath(StrEnum):
    DIRECT = "direct"
    RELAY = "relay"


@dataclass(frozen=True, slots=True)
class TransportDecision:
    path: TransportPath
    fell_back: bool = False


def choose_transport(
    mode: str,
    *,
    direct_available: bool,
    relay_configured: bool,
) -> TransportDecision:
    if mode == "direct":
        if not direct_available:
            raise BarnError(ErrorCode.CONFIGURATION, "Direct transport is unavailable")
        return TransportDecision(TransportPath.DIRECT)
    if mode == "relay":
        if not relay_configured:
            raise BarnError(ErrorCode.CONFIGURATION, "Relay transport is not configured")
        return TransportDecision(TransportPath.RELAY)
    if mode != "auto":
        raise BarnError(ErrorCode.CONFIGURATION, "Transport mode is invalid")
    if direct_available:
        return TransportDecision(TransportPath.DIRECT)
    if relay_configured:
        return TransportDecision(TransportPath.RELAY, fell_back=True)
    raise BarnError(ErrorCode.CONFIGURATION, "No Barn transport is available")


def with_failover(
    mode: str,
    direct: Callable[[], T],
    relay: Callable[[], T],
    *,
    relay_configured: bool,
) -> tuple[T, TransportDecision]:
    if mode == "relay":
        if not relay_configured:
            raise BarnError(ErrorCode.CONFIGURATION, "Relay transport is not configured")
        return relay(), TransportDecision(TransportPath.RELAY)
    if mode not in ("auto", "direct"):
        raise BarnError(ErrorCode.CONFIGURATION, "Transport mode is invalid")
    try:
        return direct(), TransportDecision(TransportPath.DIRECT)
    except (OSError, httpx.TransportError) as direct_error:
        if mode == "direct" or not relay_configured:
            raise direct_error
        try:
            return relay(), TransportDecision(TransportPath.RELAY, fell_back=True)
        except Exception as relay_error:
            raise BarnError(
                ErrorCode.CONFIGURATION, "Direct and relay transports failed"
            ) from relay_error
