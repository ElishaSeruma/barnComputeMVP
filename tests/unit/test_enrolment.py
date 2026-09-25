from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization

from barn_compute.coordinator.service import CoordinatorService
from barn_compute.crypto import create_barn_ca, load_private_identity
from barn_compute.errors import BarnError, ErrorCode
from barn_compute.models import EnrolmentStatus, NodeStatus
from barn_compute.node.service import NodeService, canonical_enrolment_proof


def setup_services(tmp_path, node_name="MacNode", host="127.0.0.1"):
    coordinator = CoordinatorService(tmp_path / "coordinator")
    coordinator_metadata = coordinator.initialize("LabBarn", "127.0.0.1")
    node = NodeService(tmp_path / node_name)
    node_metadata = node.initialize(node_name, host)
    ca_pem = (coordinator.state_dir / "ca-cert.pem").read_bytes()
    node.pin_barn_ca(ca_pem, coordinator_metadata.ca_fingerprint)
    return coordinator, node, node_metadata


def submit_node(coordinator, node, node_id, *, ttl=timedelta(minutes=10)):
    invite = coordinator.create_invite(ttl)
    challenge = coordinator.create_enrolment_challenge(invite.code, str(node_id))
    submission = node.create_submission(challenge)
    receipt = coordinator.submit_enrolment(invite.code, submission)
    node.record_receipt(receipt.request_id, receipt.receipt)
    return invite, submission, receipt


def test_two_nodes_remain_pending_until_explicit_approval(tmp_path) -> None:
    coordinator, mac, mac_metadata = setup_services(tmp_path, "MacNode")
    windows = NodeService(tmp_path / "WindowsNode")
    windows_metadata = windows.initialize("WindowsNode", "127.0.0.2")
    coordinator_metadata = coordinator.load_metadata()
    windows.pin_barn_ca(
        (coordinator.state_dir / "ca-cert.pem").read_bytes(),
        coordinator_metadata.ca_fingerprint,
    )

    _, _, mac_receipt = submit_node(coordinator, mac, mac_metadata.node_id)
    _, _, windows_receipt = submit_node(
        coordinator, windows, windows_metadata.node_id
    )

    pending = coordinator.list_pending_enrolments()
    assert {item.node_id for item in pending} == {
        str(mac_metadata.node_id),
        str(windows_metadata.node_id),
    }
    assert (
        coordinator.poll_enrolment(mac_receipt.receipt).status
        is EnrolmentStatus.AWAITING_APPROVAL
    )
    assert mac.load_metadata().status is NodeStatus.PENDING

    mac_result = coordinator.approve_enrolment(str(mac_receipt.request_id))
    approved = mac.complete_enrolment(mac_result)
    assert approved.status is NodeStatus.APPROVED
    assert approved.node_id == mac_metadata.node_id
    assert approved.barn_id == coordinator_metadata.barn_id
    assert (
        coordinator.poll_enrolment(windows_receipt.receipt).status
        is EnrolmentStatus.AWAITING_APPROVAL
    )


def test_approved_identity_and_certificate_persist_across_restart(tmp_path) -> None:
    coordinator, node, metadata = setup_services(tmp_path)
    _, _, receipt = submit_node(coordinator, node, metadata.node_id)
    first_result = coordinator.approve_enrolment(str(receipt.request_id))
    second_result = coordinator.approve_enrolment(str(receipt.request_id))

    assert first_result.certificate_pem == second_result.certificate_pem
    node.complete_enrolment(first_result)
    restarted = NodeService(node.state_dir)
    assert restarted.load_metadata().node_id == metadata.node_id
    assert restarted.load_metadata().status is NodeStatus.APPROVED
    assert (node.state_dir / "node-cert.pem").is_file()
    assert not (node.state_dir / "secrets" / "enrolment-receipt.token").exists()


def test_node_uses_distinct_identity_and_tls_keys_with_matching_csr(tmp_path) -> None:
    node = NodeService(tmp_path / "node")
    metadata = node.initialize("Node", "node.example.test")
    identity = load_private_identity(node.state_dir / "secrets" / "identity-key.pem")
    tls = load_private_identity(node.state_dir / "secrets" / "tls-key.pem")
    csr = x509.load_pem_x509_csr((node.state_dir / "node.csr.pem").read_bytes())

    assert identity.public_key().public_bytes_raw() != tls.public_key().public_bytes_raw()
    assert csr.public_key().public_bytes_raw() == tls.public_key().public_bytes_raw()
    assert csr.is_signature_valid
    assert str(metadata.node_id) in csr.subject.rfc4514_string()


def test_ca_must_be_pinned_with_matching_fingerprint(tmp_path) -> None:
    coordinator = CoordinatorService(tmp_path / "coordinator")
    metadata = coordinator.initialize("LabBarn", "localhost")
    node = NodeService(tmp_path / "node")
    node.initialize("Node", "localhost")
    ca_pem = (coordinator.state_dir / "ca-cert.pem").read_bytes()

    with pytest.raises(BarnError) as mismatch:
        node.pin_barn_ca(ca_pem, "0" * 64)
    assert mismatch.value.code == ErrorCode.NOT_AUTHENTICATED
    assert node.pin_barn_ca(ca_pem, metadata.ca_fingerprint) == metadata.ca_fingerprint


def test_submission_requires_pinned_ca(tmp_path) -> None:
    coordinator = CoordinatorService(tmp_path / "coordinator")
    coordinator.initialize("LabBarn", "localhost")
    node = NodeService(tmp_path / "node")
    metadata = node.initialize("Node", "localhost")
    invite = coordinator.create_invite(timedelta(minutes=10))
    challenge = coordinator.create_enrolment_challenge(invite.code, str(metadata.node_id))

    with pytest.raises(BarnError) as error:
        node.create_submission(challenge)
    assert error.value.code == ErrorCode.CONFIGURATION


def test_forged_identity_proof_is_rejected(tmp_path) -> None:
    coordinator, node, metadata = setup_services(tmp_path)
    invite = coordinator.create_invite(timedelta(minutes=10))
    challenge = coordinator.create_enrolment_challenge(invite.code, str(metadata.node_id))
    submission = node.create_submission(challenge).model_copy(update={"proof": b"x" * 64})

    with pytest.raises(BarnError) as error:
        coordinator.submit_enrolment(invite.code, submission)
    assert error.value.code == ErrorCode.NOT_AUTHENTICATED
    assert coordinator.list_pending_enrolments() == []


def test_challenge_is_bound_to_node_and_one_use(tmp_path) -> None:
    coordinator, node, metadata = setup_services(tmp_path)
    invite = coordinator.create_invite(timedelta(minutes=10))
    challenge = coordinator.create_enrolment_challenge(invite.code, str(uuid4()))
    submission = node.create_submission(challenge)

    with pytest.raises(BarnError) as wrong_node:
        coordinator.submit_enrolment(invite.code, submission)
    assert wrong_node.value.code == ErrorCode.NOT_AUTHENTICATED

    invite2 = coordinator.create_invite(timedelta(minutes=10))
    challenge2 = coordinator.create_enrolment_challenge(invite2.code, str(metadata.node_id))
    submission2 = node.create_submission(challenge2)
    coordinator.submit_enrolment(invite2.code, submission2)
    with pytest.raises(BarnError) as replay:
        coordinator.submit_enrolment(invite2.code, submission2)
    assert replay.value.code in {ErrorCode.NOT_AUTHORISED, ErrorCode.INVALID_REQUEST}


def test_csr_san_mismatch_is_rejected_even_with_valid_identity_proof(tmp_path) -> None:
    coordinator, node, metadata = setup_services(tmp_path)
    invite = coordinator.create_invite(timedelta(minutes=10))
    challenge = coordinator.create_enrolment_challenge(invite.code, str(metadata.node_id))
    submission = node.create_submission(challenge)
    changed_host = "other.example.test"
    identity = load_private_identity(node.state_dir / "secrets" / "identity-key.pem")
    proof = identity.sign(
        canonical_enrolment_proof(
            challenge.challenge,
            metadata.node_id,
            submission.csr_pem,
            changed_host,
            metadata.peer_port,
            submission.protocol_version,
        )
    )
    altered = submission.model_copy(
        update={"advertised_host": changed_host, "proof": proof}
    )

    with pytest.raises(BarnError) as error:
        coordinator.submit_enrolment(invite.code, altered)
    assert error.value.code == ErrorCode.INVALID_REQUEST


def test_unsupported_protocol_major_is_rejected(tmp_path) -> None:
    coordinator, node, metadata = setup_services(tmp_path)
    invite = coordinator.create_invite(timedelta(minutes=10))
    challenge = coordinator.create_enrolment_challenge(invite.code, str(metadata.node_id))
    submission = node.create_submission(challenge)
    altered = submission.model_copy(update={"protocol_version": "2.0"})

    with pytest.raises(BarnError) as error:
        coordinator.submit_enrolment(invite.code, altered)
    assert error.value.code == ErrorCode.PROTOCOL_MISMATCH


def test_expired_challenge_and_invite_are_rejected(tmp_path) -> None:
    coordinator, node, metadata = setup_services(tmp_path)
    invite = coordinator.create_invite(timedelta(minutes=1))
    challenge = coordinator.create_enrolment_challenge(invite.code, str(metadata.node_id))
    submission = node.create_submission(challenge)

    with pytest.raises(BarnError) as challenge_error:
        coordinator.submit_enrolment(
            invite.code, submission, now=challenge.expires_at + timedelta(seconds=1)
        )
    assert challenge_error.value.code == ErrorCode.NOT_AUTHORISED

    coordinator2, node2, metadata2 = setup_services(tmp_path / "second")
    invite2 = coordinator2.create_invite(timedelta(minutes=1))
    challenge2 = coordinator2.create_enrolment_challenge(invite2.code, str(metadata2.node_id))
    submission2 = node2.create_submission(challenge2)
    receipt = coordinator2.submit_enrolment(invite2.code, submission2)
    with pytest.raises(BarnError) as invite_error:
        coordinator2.approve_enrolment(
            str(receipt.request_id), now=datetime.now(UTC) + timedelta(minutes=2)
        )
    assert invite_error.value.code == ErrorCode.NOT_AUTHORISED


def test_duplicate_node_id_with_same_identity_is_rejected(tmp_path) -> None:
    coordinator, node, metadata = setup_services(tmp_path)
    submit_node(coordinator, node, metadata.node_id)
    invite = coordinator.create_invite(timedelta(minutes=10))
    challenge = coordinator.create_enrolment_challenge(invite.code, str(metadata.node_id))
    submission = node.create_submission(challenge)

    with pytest.raises(BarnError) as error:
        coordinator.submit_enrolment(invite.code, submission)
    assert error.value.code == ErrorCode.INVALID_REQUEST


def test_rejection_and_receipt_privacy(tmp_path) -> None:
    coordinator, node, metadata = setup_services(tmp_path)
    invite, _, receipt = submit_node(coordinator, node, metadata.node_id)
    database_bytes = coordinator.database_path.read_bytes()
    assert invite.code.encode() not in database_bytes
    assert receipt.receipt.encode() not in database_bytes

    coordinator.reject_enrolment(str(receipt.request_id))
    result = coordinator.poll_enrolment(receipt.receipt)
    assert result.status is EnrolmentStatus.REJECTED
    with pytest.raises(BarnError) as invalid:
        coordinator.poll_enrolment("not-a-valid-receipt-value-at-all")
    assert invalid.value.code == ErrorCode.NOT_AUTHENTICATED


def test_tampered_grant_binding_is_rejected_by_node(tmp_path) -> None:
    coordinator, node, metadata = setup_services(tmp_path)
    _, _, receipt = submit_node(coordinator, node, metadata.node_id)
    result = coordinator.approve_enrolment(str(receipt.request_id))
    tampered = result.model_copy(update={"grant_public_key": b"x" * 32})

    with pytest.raises(BarnError) as error:
        node.complete_enrolment(tampered)
    assert error.value.code == ErrorCode.NOT_AUTHENTICATED


def test_certificate_contains_expected_key_san_barn_and_grant_binding(tmp_path) -> None:
    coordinator, node, metadata = setup_services(tmp_path, host="node.example.test")
    _, _, receipt = submit_node(coordinator, node, metadata.node_id)
    result = coordinator.approve_enrolment(str(receipt.request_id))
    node.complete_enrolment(result)

    certificate = x509.load_pem_x509_certificate(result.certificate_pem)
    san = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert san.get_values_for_type(x509.DNSName) == ["node.example.test"]
    tls_key = load_private_identity(node.state_dir / "secrets" / "tls-key.pem")
    assert certificate.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ) == tls_key.public_key().public_bytes_raw()


def test_conflicting_identity_key_for_existing_node_id_is_rejected(tmp_path) -> None:
    coordinator, node, metadata = setup_services(tmp_path)
    _, original, _ = submit_node(coordinator, node, metadata.node_id)
    invite = coordinator.create_invite(timedelta(minutes=10))
    challenge = coordinator.create_enrolment_challenge(invite.code, str(metadata.node_id))
    attacker_key = load_private_identity(node.state_dir / "secrets" / "tls-key.pem")
    attacker_public = attacker_key.public_key().public_bytes_raw()
    proof = attacker_key.sign(
        canonical_enrolment_proof(
            challenge.challenge,
            metadata.node_id,
            original.csr_pem,
            metadata.advertised_host,
            metadata.peer_port,
            original.protocol_version,
        )
    )
    conflicting = original.model_copy(
        update={
            "challenge": challenge.challenge,
            "identity_public_key": attacker_public,
            "proof": proof,
        }
    )

    with pytest.raises(BarnError) as error:
        coordinator.submit_enrolment(invite.code, conflicting)
    assert error.value.code == ErrorCode.NOT_AUTHORISED


def test_malformed_csr_is_rejected_after_valid_identity_proof(tmp_path) -> None:
    coordinator, node, metadata = setup_services(tmp_path)
    invite = coordinator.create_invite(timedelta(minutes=10))
    challenge = coordinator.create_enrolment_challenge(invite.code, str(metadata.node_id))
    submission = node.create_submission(challenge)
    malformed = b"-----BEGIN CERTIFICATE REQUEST-----\ninvalid\n"
    identity = load_private_identity(node.state_dir / "secrets" / "identity-key.pem")
    proof = identity.sign(
        canonical_enrolment_proof(
            challenge.challenge,
            metadata.node_id,
            malformed,
            metadata.advertised_host,
            metadata.peer_port,
            submission.protocol_version,
        )
    )
    altered = submission.model_copy(update={"csr_pem": malformed, "proof": proof})

    with pytest.raises(BarnError) as error:
        coordinator.submit_enrolment(invite.code, altered)
    assert error.value.code == ErrorCode.INVALID_REQUEST


def test_consumed_invite_cannot_issue_another_challenge(tmp_path) -> None:
    coordinator, node, metadata = setup_services(tmp_path)
    invite, _, receipt = submit_node(coordinator, node, metadata.node_id)
    coordinator.approve_enrolment(str(receipt.request_id))

    with pytest.raises(BarnError) as error:
        coordinator.create_enrolment_challenge(invite.code, str(uuid4()))
    assert error.value.code == ErrorCode.NOT_AUTHORISED


def test_node_rejects_result_from_unpinned_ca(tmp_path) -> None:
    coordinator, node, metadata = setup_services(tmp_path)
    _, _, receipt = submit_node(coordinator, node, metadata.node_id)
    result = coordinator.approve_enrolment(str(receipt.request_id))
    _, other_ca = create_barn_ca(str(uuid4()), "Other")
    tampered = result.model_copy(
        update={
            "ca_certificate_pem": other_ca.public_bytes(serialization.Encoding.PEM)
        }
    )

    with pytest.raises(BarnError) as error:
        node.complete_enrolment(tampered)
    assert error.value.code == ErrorCode.NOT_AUTHENTICATED
