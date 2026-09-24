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

## Active slice: coordinator trust and enrolment

1. Create durable coordinator state and SQLite migrations.
2. Generate the Barn ID, Barn CA, coordinator TLS identity, grant-signing
   identity, and loopback admin token.
3. Export the public CA and display its SHA-256 fingerprint.
4. Create hashed, expiring, one-use invitation records.
5. Add node identity creation, certificate requests, proof of possession,
   pending enrolments, explicit approval, and certificate issuance.
6. Add local multi-node tests for approval, rejection, replay, expiry,
   persistence, and duplicate identity handling.

## Following slices

1. Coordinator and node HTTPS services plus loopback admin APIs.
2. Signed heartbeat, registry refresh, liveness state, and diagnostics.
3. Immutable managed-file import and manifests.
4. Shares, grants, peer HTTPS, resumable chunk transfer, and final integrity.
5. Secure outbound-only relay transport and direct-to-relay failover.
6. Complete automated security and packaging gates.
7. Owner-authorised TestPyPI release and physical macOS/Windows acceptance.

