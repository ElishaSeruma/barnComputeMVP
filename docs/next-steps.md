# Delivery status and next steps

## Completed foundation checkpoint

- Package metadata, `src/` layout, and `barn` entry point.
- Python 3.11/3.12 dependency constraints and Apache 2.0 packaging.
- Strict configuration and protocol models.
- Ed25519 signed-request canonicalisation and verification.
- Durable SQLite nonce replay protection and clock-skew rejection.
- Private identity persistence and platform-aware state directories.
- Initial command hierarchy, diagnostics, tests, and Windows/macOS CI.
- Local Windows and Apple Silicon macOS lint, unit-test, build, and Twine
  validation.

These checks validate the development foundation only. They are not TestPyPI or
physical two-node M1 acceptance.

## Completed coordinator-bootstrap checkpoint

- Atomic durable coordinator state initialization.
- Initial SQLite schema and migration tracking.
- Barn ID, Ed25519 Barn CA, SAN-bound coordinator TLS identity, independent
  grant-signing identity, and loopback admin token.
- Public CA export with matching SHA-256 fingerprint.
- Hashed, expiring, one-use invitation creation with bounded TTL.
- Duplicate initialization refusal and private/public key separation tests.
- Disposable CLI initialization, CA export, and invitation workflow.

This checkpoint was reverified on Windows on 2026-09-25: Ruff passed, all 18
tests passed with 84% coverage, wheel and sdist builds succeeded, and Twine
validated both artifacts. The expanded coordinator suite still needs to be
recorded on macOS.

## Active phase: node identity and explicit enrolment

1. Add durable node state with a random Node ID and local Ed25519 identity.
2. Generate a TLS CSR with a SAN matching the explicitly advertised node IP or
   hostname.
3. Add an enrolment challenge and signed proof of identity-key possession.
4. Validate invitation digest, expiry, one-use state, and protocol version while
   keeping a valid request pending until explicit approval.
5. Persist a high-entropy, request-bound receipt for limited status polling.
6. Implement pending-enrolment listing plus explicit approve and reject actions.
7. On approval, consume the invitation, register the node key, issue the node
   certificate idempotently, and deliver the coordinator grant public key bound
   to the trusted Barn response.
8. Reject invalid proofs, malformed or mismatched CSRs, expired/reused invites,
   duplicate Node IDs with conflicting keys, and unsupported protocol majors.
9. Add persistence and negative tests using two simulated nodes and isolated
   state directories.

### Exit gate for this phase

- Two different simulated nodes can initialize and submit independent pending
  requests.
- Neither node gains membership before coordinator approval.
- Approval issues the expected certificate and persists the same Node ID across
  restart.
- Expired, reused, malformed, forged, and conflicting requests are rejected.
- Ruff, unit/security tests, package build, and Twine checks pass on Windows and
  macOS.

## Following slices

1. Coordinator and node HTTPS services plus loopback admin APIs, exposing the
   tested enrolment workflow over verified TLS.
2. Signed heartbeat, registry refresh, liveness state, and diagnostics.
3. Immutable managed-file import and manifests.
4. Shares, grants, peer HTTPS, resumable chunk transfer, and final integrity.
5. Secure outbound-only relay transport and direct-to-relay failover.
6. Complete automated security and packaging gates.
7. Owner-authorised TestPyPI release and physical macOS/Windows acceptance.
