# Delivery status and next steps

## Current next steps - 2026-10-01

The integrated M1 runtime exists and `0.1.0a1` was published to TestPyPI.
Physical Mac/Windows direct transfers, recovery, authorization denials and
concurrent transfers have recorded passing evidence. M1 is still **NOT ACCEPTED**.
Use [the canonical report](test-report.md),
[physical evidence](M1_PHYSICAL_TEST_RESULTS_2026-09-29.md) and
[closure gates](M1_CLOSURE_AND_GATE.md) for current status.

1. C1 documentation reconciliation and the fresh Windows baseline are complete:
   Ruff, 82 tests, 82% coverage, build, Twine and existing archive screening pass.
   See [the dated record](M1_BASELINE_2026-09-30.md). Historical Mac/Windows
   results remain evidence for their tested revisions; no fresh Mac run is claimed.
2. C2 is complete on both hosts. [October 1 evidence](M1_C2_PROVENANCE_2026-10-01.md)
   records fresh TestPyPI installs, retained redacted logs, wheel/content
   comparisons, `pip check`, versions and local HTTPS coordinator/node smoke checks.
   Preserve the evidence; no further installation rerun is required for this gate.
3. Install the unpublished `0.1.0a2` correction candidate on both hosts and
   complete the C3 retest. The [October 1 physical run](M1_C3_RESOURCE_RESULTS_2026-10-01.md)
   produced a successful synchronized bidirectional transfer but exposed a
   retained 100 MiB `assembled.tmp` per transfer. The cleanup fix, 84-test
   regression run, clean wheel check and candidate hashes are recorded there;
   repeat the synchronized run with no retained transfer temporary files.
4. C5 source implementation and local isolation tests are complete; see the
   [dated control-path record](M1_C5_CONTROL_PATH_2026-10-01.md). Arrange C4's
   owner-approved public host, DNS and TLS, then run the physical C4/C5 matrix.
5. Complete C4/C5 physical tests: secure forced relay, direct-to-relay resume,
   failures, revocation and recovery, then control and data operations with
   cross-device LAN connectivity blocked and outbound TCP 443 available.
6. Review actual evidence for every closure gate before marking M1 accepted.
   Preserve historical records and record later runs in new dated files.

Passed destructive physical tests need not be repeated merely for presentation;
rerun relevant checks when a changed artifact requires regression evidence.
The unexplained initial Windows-to-Mac failure remains a known observation.

M2 follows [START_HERE_M2_CODEX.md](START_HERE_M2_CODEX.md) and
[the M2 specification](M2_1_TO_M2_9_IMPLEMENTATION_SPEC.md): BRG, NBO ledger,
Bays, encrypted fragments, distribution matrix, Placement NBO, DT-NBO,
source-independent retrieval, then Resilience NBO. Development can overlap
external M1 closure testing; TestPyPI release remains gated by inherited M1
network/security closure and [the release plan](TESTPYPI_0_2_0A1_ACCEPTANCE_PLAN.md).
Use the [ordered M2 build plan](M2_BUILD_PLAN.md) for implementation slices and
the [M1 closure workspace](m1-closure/README.md) for explicit gate criteria.
This documentation slice does not implement M2 or change the runtime.

## Historical delivery checkpoints

Everything below records earlier development stages, including their then-open
gates. It is preserved for traceability and is not the current work queue.

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

### Relay policy checkpoint

The fail-closed transport policy foundation is complete on Windows as of
2026-09-26. `direct`, `relay`, and `auto` modes now have explicit selection
rules; `auto` prefers direct HTTPS and may fall back only to a configured relay,
while forced modes fail closed. The policy is covered by 60 passing tests at
79% coverage.

The separately deployed WSS relay service, admission tickets, inner protected
peer sessions, and physical relay failover remain pending.

### Relay admission checkpoint

The signed relay-admission slice is complete on Windows as of 2026-09-26.
Coordinators issue five-minute, Barn-scoped tickets; the relay validates the
grant-key signature, expiry, and peer membership before admitting a WSS
connection. Opaque frames are bounded to 1 MiB and routed only to the ticket's
peer; the relay has no file-grant authority. Ruff passes and the full suite
passes with 61 tests and 79% coverage.

Inner authenticated/encrypted peer sessions, production relay deployment,
ticket retrieval surfaces, and physical failover remain pending.

### Inner session and ticket retrieval checkpoint

The inner-session foundation is complete on Windows as of 2026-09-26. The
authenticated control plane can retrieve a five-minute signed relay ticket,
and peers can derive the same X25519/HKDF session key and protect opaque relay
frames with ChaCha20-Poly1305 associated data. Ruff passes and the full suite
passes with 62 tests at 79% coverage.

Binding the session handshake to node certificate identity, production relay
deployment, physical failover, and full cross-platform security verification
remain pending.

### Identity-bound inner handshake checkpoint

The inner session hello now binds the node UUID and ephemeral X25519 public key
to the enrolled Ed25519 identity signature and negotiated transcript. Receivers
reject a different identity or transcript before deriving the encrypted
session. Ruff passes and the Windows suite passes with 63 tests. macOS must
rerun the full suite before this checkpoint is accepted cross-platform.

### Current Windows checkpoint

The coordinator/node transport slice is implemented on Windows. It includes
the public HTTPS enrolment API, request-bound polling, loopback-only admin APIs,
the CA-verifying node client, paired foreground service runners, and the signed
heartbeat/registry routes. Ruff and 47 tests pass with 81% coverage. macOS
verification for the newer transport and heartbeat slices is the next release
gate; the previous 38-test Mac checkpoint remains valid only for the
persistence-first implementation.

## Following slices

The integrated runtime supersedes the isolated checkpoints above. Real local
HTTPS/WSS transfer tests and signed remote workflows are now implemented.
Windows source verification passed all 82 tests without skips at 82% coverage;
the independent installed-wheel suite also passed. Detailed results are in
`WINDOWS_M1_RUNTIME_VERIFICATION.md`.
The current completion gates are:

1. Run the complete updated suite and packaging checks on Mac, following
   `docs/M1_ACCEPTANCE_RUNBOOK.md`; record the tested commit and results.
2. Deploy the separately configured public WSS relay and test both physical
   transfer directions, interruption, recovery, revocation and blocked-direct
   fallback. Coordinator HTTPS access is required on both hosts.
3. Provide TestPyPI credentials/package ownership, publish the inspected
   release candidate, and install that artifact on both physical machines.
4. Review all evidence and mark M1 ACCEPTED only when every release gate passes.
