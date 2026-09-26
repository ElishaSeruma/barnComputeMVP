from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from barn_compute.coordinator.service import CoordinatorService, canonical_transfer_grant
from barn_compute.crypto import load_private_identity, load_public_key, public_key_bytes
from barn_compute.errors import BarnError, ErrorCode
from barn_compute.node.service import NodeService


def approved_nodes(tmp_path):
    coordinator = CoordinatorService(tmp_path / "coordinator")
    metadata = coordinator.initialize("LabBarn", "127.0.0.1")
    nodes = []
    for name, host in (("MacNode", "127.0.0.1"), ("WindowsNode", "127.0.0.2")):
        node = NodeService(tmp_path / name)
        node_metadata = node.initialize(name, host)
        node.pin_barn_ca(
            (coordinator.state_dir / "ca-cert.pem").read_bytes(), metadata.ca_fingerprint
        )
        invite = coordinator.create_invite(timedelta(minutes=10))
        challenge = coordinator.create_enrolment_challenge(invite.code, str(node_metadata.node_id))
        receipt = coordinator.submit_enrolment(invite.code, node.create_submission(challenge))
        node.record_receipt(receipt.request_id, receipt.receipt)
        node.complete_enrolment(coordinator.approve_enrolment(str(receipt.request_id)))
        nodes.append(node)
    return coordinator, nodes


def test_share_issues_recipient_bound_short_lived_signed_grant(tmp_path) -> None:
    coordinator, (source, recipient) = approved_nodes(tmp_path)
    now = datetime.now(UTC)
    share = coordinator.create_share(
        uuid4(), source.load_metadata().node_id, recipient.load_metadata().node_id,
        timedelta(hours=1), now=now,
    )

    grant = coordinator.issue_transfer_grant(
        share.share_id, recipient.load_metadata().node_id, now=now
    )
    public_key = load_public_key(
        public_key_bytes(
            load_private_identity(coordinator.state_dir / "secrets" / "grant-key.pem").public_key()
        )
    )
    public_key.verify(
        grant.signature,
        canonical_transfer_grant(
            grant.grant_id, grant.share_id, grant.transfer_id, grant.file_id,
            grant.source_node_id, grant.recipient_node_id, grant.issued_at, grant.expires_at,
        ),
    )
    assert grant.expires_at == now + timedelta(minutes=5)


def test_share_rejects_wrong_recipient_expiry_and_revocation(tmp_path) -> None:
    coordinator, (source, recipient) = approved_nodes(tmp_path)
    other = NodeService(tmp_path / "Other")
    other.initialize("Other", "127.0.0.3")
    share = coordinator.create_share(
        uuid4(), source.load_metadata().node_id, recipient.load_metadata().node_id,
        timedelta(seconds=10),
    )
    with pytest.raises(BarnError) as wrong_recipient:
        coordinator.issue_transfer_grant(share.share_id, other.load_metadata().node_id)
    assert wrong_recipient.value.code is ErrorCode.NOT_AUTHORISED

    coordinator.revoke_share(share.share_id)
    with pytest.raises(BarnError) as revoked:
        coordinator.issue_transfer_grant(share.share_id, recipient.load_metadata().node_id)
    assert revoked.value.code is ErrorCode.NOT_AUTHORISED

    expired = coordinator.create_share(
        uuid4(), source.load_metadata().node_id, recipient.load_metadata().node_id,
        timedelta(seconds=1), now=datetime.now(UTC) - timedelta(minutes=1),
    )
    with pytest.raises(BarnError) as expired_error:
        coordinator.issue_transfer_grant(expired.share_id, recipient.load_metadata().node_id)
    assert expired_error.value.code is ErrorCode.NOT_AUTHORISED
