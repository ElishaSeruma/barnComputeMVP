from pathlib import Path

import httpx
import pytest

from barn_compute.coordinator.admin_client import CoordinatorAdminClient
from barn_compute.errors import BarnError, ErrorCode
from barn_compute.node.client import CoordinatorClient


def test_node_client_refuses_plain_http(tmp_path: Path) -> None:
    with pytest.raises(BarnError, match="must use HTTPS") as error:
        CoordinatorClient("http://coordinator.example", tmp_path / "ca.pem")
    assert error.value.code is ErrorCode.CONFIGURATION


def test_admin_client_authenticates_and_maps_safe_errors(tmp_path: Path) -> None:
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "admin.token").write_text("private-token", encoding="ascii")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer private-token"
        return httpx.Response(
            401,
            json={
                "error": {
                    "code": "NOT_AUTHENTICATED",
                    "message": "Admin token is invalid",
                    "request_id": "test",
                }
            },
        )

    with CoordinatorAdminClient(
        tmp_path,
        "http://127.0.0.1:8754",
        transport=httpx.MockTransport(handler),
    ) as client, pytest.raises(BarnError, match="Admin token is invalid") as error:
        client.list_enrolments()
    assert error.value.code is ErrorCode.NOT_AUTHENTICATED
