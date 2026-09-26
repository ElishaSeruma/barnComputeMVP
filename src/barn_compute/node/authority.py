"""Live coordinator checks and recipient proof for peer delivery."""

from __future__ import annotations

from fastapi import Request

from ..api_models import encode_binary
from ..auth import NonceStore, SignedRequest, verify_request
from ..crypto import load_public_key
from ..errors import BarnError, ErrorCode
from ..models import TransferGrant
from .client import CoordinatorClient
from .service import NodeService


def grant_payload(grant: TransferGrant) -> dict:
    return {
        **grant.model_dump(mode="json", exclude={"signature"}),
        "signature": encode_binary(grant.signature),
    }


class PeerAuthority:
    def __init__(self, node: NodeService, coordinator: CoordinatorClient):
        self.node = node
        self.coordinator = coordinator

    def validate(self, grant: TransferGrant) -> None:
        self.node._verify_transfer_grant(grant)
        self.coordinator.signed(self.node, "POST", "/v1/grants/validate", grant_payload(grant))

    def __call__(self, grant: TransferGrant, request: Request) -> None:
        if request.headers.get("x-barn-node-id") != str(grant.recipient_node_id):
            raise BarnError(ErrorCode.NOT_AUTHORISED, "Recipient identity does not match grant")
        self.validate(grant)
        key = self.coordinator.peer_key(self.node, grant.recipient_node_id)
        try:
            signed = SignedRequest(
                method=request.method,
                target=request.url.path + (f"?{request.url.query}" if request.url.query else ""),
                timestamp=request.headers["x-barn-timestamp"],
                nonce=request.headers["x-barn-nonce"],
                signature=request.headers["x-barn-signature"],
            )
        except KeyError as exc:
            raise BarnError(ErrorCode.NOT_AUTHENTICATED, "Recipient proof is required") from exc
        with NonceStore(self.node.state_dir / "peer-nonces.db") as store:
            verify_request(load_public_key(key), signed, str(grant.recipient_node_id), store)
