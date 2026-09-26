import pytest

from barn_compute.errors import BarnError, ErrorCode
from barn_compute.transport import TransportPath, choose_transport, with_failover


def test_auto_prefers_direct_and_falls_back_to_configured_relay() -> None:
    assert (
        choose_transport("auto", direct_available=True, relay_configured=True).path
        is TransportPath.DIRECT
    )
    decision = choose_transport("auto", direct_available=False, relay_configured=True)
    assert decision.path is TransportPath.RELAY
    assert decision.fell_back


def test_transport_modes_fail_closed() -> None:
    with pytest.raises(BarnError) as error:
        choose_transport("direct", direct_available=False, relay_configured=True)
    assert error.value.code is ErrorCode.CONFIGURATION
    with pytest.raises(BarnError):
        choose_transport("relay", direct_available=False, relay_configured=False)


def test_with_failover_uses_relay_only_after_direct_failure() -> None:
    result, decision = with_failover(
        "auto", lambda: (_ for _ in ()).throw(OSError("direct")), lambda: "relay",
        relay_configured=True,
    )
    assert result == "relay"
    assert decision.path is TransportPath.RELAY
    assert decision.fell_back


def test_direct_mode_does_not_fallback() -> None:
    with pytest.raises(OSError):
        with_failover(
            "direct", lambda: (_ for _ in ()).throw(OSError("direct")), lambda: "relay",
            relay_configured=True,
        )
