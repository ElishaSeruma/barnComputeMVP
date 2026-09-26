"""Authenticated client for the coordinator loopback administration API."""

from __future__ import annotations

from datetime import timedelta
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from ..errors import BarnError, ErrorCode


class CoordinatorAdminClient:
    def __init__(
        self,
        state_dir: Path,
        base_url: str,
        *,
        timeout: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        parsed = urlsplit(base_url)
        try:
            loopback = ip_address(parsed.hostname or "").is_loopback
        except ValueError:
            loopback = False
        if (
            not loopback
            or parsed.scheme != "http"
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise BarnError(ErrorCode.CONFIGURATION, "Admin URL must use a loopback HTTP IP")
        token = (state_dir / "secrets" / "admin.token").read_text(encoding="ascii").strip()
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
            follow_redirects=False,
            transport=transport,
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> CoordinatorAdminClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        try:
            return self.client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise BarnError(
                ErrorCode.CONFIGURATION,
                "Coordinator admin service is unavailable; start the coordinator",
            ) from exc

    @staticmethod
    def _payload(response: httpx.Response) -> object:
        if response.is_success:
            return response.json() if response.content else None
        try:
            error = response.json()["error"]
            raise BarnError(ErrorCode(error["code"]), error["message"])
        except (KeyError, TypeError, ValueError) as exc:
            raise BarnError(
                ErrorCode.INVALID_REQUEST,
                f"Coordinator admin service returned HTTP {response.status_code}",
            ) from exc

    def create_invite(self, ttl: timedelta) -> dict[str, object]:
        response = self._request(
            "POST", "/local/v1/invites", json={"ttl_seconds": int(ttl.total_seconds())}
        )
        return dict(self._payload(response))

    def list_enrolments(self) -> list[dict[str, object]]:
        response = self._request("GET", "/local/v1/enrolments")
        return list(self._payload(response))

    def approve(self, request_id: str) -> dict[str, object]:
        response = self._request("POST", f"/local/v1/enrolments/{request_id}/approve")
        return dict(self._payload(response))

    def reject(self, request_id: str) -> None:
        response = self._request("POST", f"/local/v1/enrolments/{request_id}/reject")
        self._payload(response)

    def create_share(
        self,
        file_id: UUID,
        source_node_id: UUID,
        recipient_node_id: UUID,
        ttl: timedelta,
    ) -> dict[str, object]:
        response = self._request(
            "POST",
            "/local/v1/shares",
            json={
                "file_id": str(file_id),
                "source_node_id": str(source_node_id),
                "recipient_node_id": str(recipient_node_id),
                "ttl_seconds": int(ttl.total_seconds()),
            },
        )
        return dict(self._payload(response))

    def list_shares(self) -> list[dict[str, object]]:
        response = self._request("GET", "/local/v1/shares")
        return list(self._payload(response))

    def revoke_share(self, share_id: UUID) -> None:
        response = self._request("POST", f"/local/v1/shares/{share_id}/revoke")
        self._payload(response)

    def issue_grant(self, share_id: UUID, recipient_node_id: UUID) -> dict[str, object]:
        response = self._request(
            "POST",
            f"/local/v1/shares/{share_id}/grant",
            params={"recipient_node_id": str(recipient_node_id)},
        )
        return dict(self._payload(response))

    def issue_relay_ticket(
        self, source_node_id: UUID, recipient_node_id: UUID, ttl: timedelta = timedelta(minutes=5)
    ) -> dict[str, object]:
        response = self._request(
            "POST",
            "/local/v1/relay/tickets",
            params={
                "source_node_id": str(source_node_id),
                "recipient_node_id": str(recipient_node_id),
                "ttl_seconds": int(ttl.total_seconds()),
            },
        )
        return dict(self._payload(response))
