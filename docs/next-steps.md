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

This checkpoint was reverified on both platforms on 2026-09-25. Windows passed
Ruff, all 18 tests with 84% coverage, wheel/sdist builds, and Twine validation.
The Apple Silicon Mac passed the same 18-test suite with 84% coverage, editable
and clean-wheel installation, build and Twine validation, CA export safety,
matching CA fingerprints, one-use invitation creation, and duplicate-init
rejection. The coordinator-bootstrap checkpoint is therefore complete.

## Phase readiness decision

The project is ready to begin node identity and explicit enrolment. This means
the completed bootstrap layer is stable enough to build on; it does not mean M1
or the release candidate is complete. TestPyPI provenance, physical two-node
acceptance, file transfers, and relay behavior remain `NOT RUN`.

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

### Windows implementation checkpoint

The persistence-first implementation is complete on Windows as of 2026-09-25.
Ruff passes; 38 tests pass with 85% coverage; wheel/sdist build and Twine checks
pass. The implementation includes every item above at the service and repository
layers. `barn node init`, pending-enrolment listing, approval, and rejection have
CLI surfaces. `barn node enroll` remains intentionally unavailable until the
verified HTTPS API carries this workflow.

The matching Mac checkpoint passed at commit
`6cb8c815c2854e2814c41ededf1e00bf1b8cebea`: 38 tests with 85% coverage,
focused enrolment tests, build, Twine, wheel inspection, clean-wheel
installation, node initialization, and duplicate-init protection all passed.
Detailed evidence is in
`docs/mac_test_results/2026-09-25-node-enrolment-38.md`.

The node identity and persistence-first enrolment phase is complete.

### Exit gate for this phase

- Two different simulated nodes can initialize and submit independent pending
  requests.
- Neither node gains membership before coordinator approval.
- Approval issues the expected certificate and persists the same Node ID across
  restart.
- Expired, reused, malformed, forged, and conflicting requests are rejected.
- Ruff, unit/security tests, package build, and Twine checks pass on Windows and
  macOS.

### Heartbeat and registry checkpoint

The signed heartbeat and registry slice is complete on Windows as of
2026-09-26. Ruff passes; 47 tests pass with 81% coverage. The implementation
includes durable heartbeat sequence state, signed heartbeat and registry HTTP
routes, nonce and sequence replay protection, storage and software metadata,
liveness transitions, registry caching, and node CLI commands for heartbeat,
registry refresh, and local node listing.

The remaining release gates are cross-platform verification, physical
two-node acceptance, managed-file transfer, and relay behavior.

### Managed-file import checkpoint

The immutable managed-file import slice is complete on Windows as of
2026-09-26. It provides private UUID-addressed storage, atomic staging-copy
imports, fixed 1 MiB chunk manifests, whole-file and per-chunk SHA-256 hashes,
zero-byte file support, the 512 MiB size limit, free-space checks, manifest
validation, and `barn file add` / `barn file list` commands. Ruff passes and
the full suite passes with 50 tests and 80% coverage.

This checkpoint does not include shares, peer serving, transfer sessions,
resume journals, or relay transport.

### Share and grant checkpoint

The recipient-scoped share and transfer-grant authority slice is complete on
Windows as of 2026-09-26. It provides durable share records, approved-node
authorization, bounded one-second-to-30-day expiry, revocation, recipient
binding, five-minute transfer grants, and Ed25519 signatures over the complete
grant scope. Ruff passes and the full suite passes with 52 tests and 80%
coverage.

Peer HTTPS serving, share HTTP/CLI surfaces, chunk transfer, resume journals,
and relay transport remain separate stages.

### Peer delivery checkpoint

The grant-authenticated peer delivery slice is complete on Windows as of
2026-09-26. Approved source nodes now expose grant-validated manifest and fixed
chunk endpoints over their existing Barn-CA HTTPS listener. Delivery checks
grant signatures, expiry, source and file scope, manifest ownership, chunk
bounds, and per-chunk SHA-256 integrity. Ruff passes and the full suite passes
with 53 tests and 80% coverage.

Durable transfer sessions, recipient-side journals, resume, final assembly,
share HTTP/CLI surfaces, and relay transport remain separate stages.

### Transfer journal checkpoint

The durable recipient-side transfer slice is complete on Windows as of
2026-09-26. It persists transfer journals after each verified fixed-size chunk,
reuses completed chunks after restart, assembles only complete manifests,
checks final size and SHA-256, and exports through a no-clobber destination
operation. Ruff passes and the full suite passes with 54 tests and 80% coverage.

The remaining gaps are share HTTP/CLI surfaces, live network download
orchestration, cancellation, and relay transport.

### Share control-plane checkpoint

The share control-plane surface is complete on Windows as of 2026-09-26. The
loopback admin API and CLI now support authenticated share creation, listing,
revocation, and signed transfer-grant issuance. Ruff passes and the full suite
passes with 55 tests and 79% coverage.

Live download orchestration, cancellation, and relay transport remain outside
this checkpoint.

### Live download checkpoint

Live recipient download orchestration is complete on Windows as of 2026-09-26.
`barn share fetch` obtains a short-lived grant, retrieves the manifest and
fixed-size chunks over CA-verified HTTPS, persists each verified chunk through
the recipient journal, resumes already completed chunks, and performs final
integrity-checked no-clobber export. Ruff passes and the full suite passes with
56 tests and 79% coverage.

Cancellation leaves the durable journal available for a later resume. Relay
transport and richer cancellation/status controls remain separate work.

### Current Windows checkpoint

The coordinator/node transport slice is implemented on Windows. It includes
the public HTTPS enrolment API, request-bound polling, loopback-only admin APIs,
the CA-verifying node client, paired foreground service runners, and the signed
heartbeat/registry routes. Ruff and 47 tests pass with 81% coverage. macOS
verification for the newer transport and heartbeat slices is the next release
gate; the previous 38-test Mac checkpoint remains valid only for the
persistence-first implementation.

## Following slices

1. **Verification gate:** run the HTTPS/admin test runbook on Apple Silicon and
   record the evidence under `docs/mac_test_results`.
2. **Next implementation:** relay transport and direct-to-relay failover.
3. Complete automated security and packaging gates.
4. Owner-authorised TestPyPI release and physical macOS/Windows acceptance.
