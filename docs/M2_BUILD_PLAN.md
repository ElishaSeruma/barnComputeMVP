# M2 build plan: M2.1 through M2.9

Status: planning only, 2026-10-01. No M2 runtime is implemented or accepted by
this document. This plan is subordinate to
[the implementation specification](M2_1_TO_M2_9_IMPLEMENTATION_SPEC.md),
[the BRG/NBO specification](BRG_AND_NBO_V0_SPEC.md), and
[the release acceptance plan](TESTPYPI_0_2_0A1_ACCEPTANCE_PLAN.md).

## Starting point and gates

- M1 `0.1.0a1` is published to TestPyPI. C1 and C2 have evidence-backed PASS
  verdicts. The physical direct-transfer record is real, but M1 is not accepted.
- C3 is RETEST REQUIRED: synchronized 100 MiB transfers passed, but both hosts
  retained completed `assembled.tmp` files. The cleanup fix is in source and in
  an unpublished `0.1.0a2` correction-candidate wheel; neither its Mac physical
  rerun nor its publication has happened.
- C4 is NOT RUN: there is no approved public relay host, DNS name or TLS
  certificate. C5 has source implementation and local real-TLS/WSS evidence,
  but its client-isolated physical test is NOT RUN.
- The `0.1.0a2` candidate had an 84-test passing Windows run. A later
  exact-source full-suite run was not clean because real-WSS startup timed out
  and the Windows host subsequently reported out-of-memory. Re-run on a
  healthy host before treating the candidate as fully verified.
- M2 development may proceed in parallel with M1 closure. Do not upload or
  accept `0.2.0a1` while inherited M1 C3-C5 defects/gates remain unresolved.
  Use [the M1 closure folder](m1-closure/README.md) for the exact exit criteria.

Before the first code slice, capture the current Git status and base SHA, keep
existing uncommitted changes, run the existing M1 suite, and record its result.
Read `README.md`, `architecture.md`, `protocol-v1.md`, `M1_ACCEPTANCE_RUNBOOK.md`,
the current M1 physical records and `test-report.md` in full. Use a separate
feature branch when practical; do not silently replace or migrate live state.

## Build rules applying to every slice

1. Keep the M1 identity, enrolment, share, grant, direct/relay transport and
   resume semantics working. Package `barnCompute`, import `barn_compute`, CLI
   `barn` and the existing wire major remain distinct compatibility concerns.
2. Use coordinator-owned SQLite for BRG, NBO and matrix authority. Node storage
   metadata and bytes stay under private node state. Introduce schema changes
   through tested, transactional/idempotent migrations. Back up copies of M1
   state before any physical upgrade; preserve IDs, CA, managed files, shares
   and journals. No implicit conversion of M1 managed files into Bays.
3. Keep the flow `BRG snapshot -> NBO decision -> immutable ledger -> planner ->
   executor -> measured outcome -> BRG observation`. NBO evaluation is pure;
   no placement, route/source choice or repair target bypasses it.
4. Use opaque IDs in telemetry and decisions. Never put paths, file content,
   tokens, keys, tickets or invite codes in BRG/NBO logs or package archives.
   Remote observations and storage operations need signed, scoped authority.
5. Keep 1 MiB M1 transport chunks separate from M2 storage fragments (proposed
   8 MiB default). Bound memory, concurrency, request sizes, retained history
   and timeouts. Make policy/weights versioned configuration, not wire constants.
6. Finish each slice with tests, migration/security review, CLI/API docs and an
   evidence note: Git SHA, files/migrations, commands, tests/coverage, platform,
   compatibility, security, limitations and the next gate. Mark unrun checks
   NOT RUN, never PASS by inference.

## Ordered implementation slices

### M2.1 - BRG v0

Implement coordinator repository/migration for node snapshots, directional
link observations, storage/availability observations and deterministic rolling
aggregates. Ingest bounded, signed node observations; hook successful and
failed M1 transfers into BRG without changing their authorization decisions.
Collect safe free-space/fragment-count snapshots. Retain raw history for a
configurable bounded period while keeping aggregates; use stable Node IDs, not
IP addresses. Add `barn brg nodes`, `barn brg node <NODE_ID>`, `barn brg links`
with human and `--json` output.

Exit: unit tests for validation/retention/aggregates and integration tests for
two distinct nodes, A->B versus B->A, direct versus relay, failure-after-success
history, signed-ingest rejection and restart persistence. Map to M201-M203.
The BRG data and queries must be usable by M2.2, but no NBO placement occurs yet.

### M2.2 - NBO framework and decision/outcome ledger

Define a versioned `NBO.evaluate(context) -> Decision` interface with pure,
deterministic evaluation and stable tie-breaks. Persist immutable decisions,
all candidates (including hard-filter rejections), component scores, reason
codes, policy/version and BRG snapshot reference. Persist executor outcomes
separately with a decision ID; failures do not rewrite decisions. Add audit-safe
`barn nbo decisions` and `barn nbo decision <DECISION_ID>` plus `--json`.

Exit: replaying an identical fixture yields the same selected action; a failed
execution creates a failed linked outcome; restart retains both; JSON/log scans
find no secret material. Map to M204-M206. The framework alone does not imply
Placement, DT or Resilience behavior has been implemented.

### M2.3 - Bay model

Migrate coordinator state for Bay, LogicalFile and immutable FileVersion with
owner, policy, `STANDARD_2X`, replication factor and encryption policy. Define
unambiguous version lookup when display names repeat. Add create/list/show,
add/files/get/health CLI surfaces incrementally, with add/get clearly blocked
or unavailable until the fragment pipeline is implemented. Offer an explicit
operator action for importing an existing M1 managed file; do not convert it
automatically. Defer deletion unless retention and replica cleanup are specified.

Exit: restart persistence, ownership checks, immutable version metadata,
duplicate-name disambiguation and no local path used as remote identity.
M207 is complete here; M208 and retrieval-related cases wait for later slices.

### M2.4 - Encrypted storage fragments

Define immutable version manifests and fragment identities, offsets, lengths,
plaintext/ciphertext SHA-256 and AEAD metadata. Use independently encrypted
fragments, a random per-file 256-bit DEK, unique nonce per fragment, and AAD
binding Barn/Bay/version/fragment/index/length/format. Persist the DEK only
wrapped by a coordinator-local KEK in private state. Nodes store ciphertext
only. Implement a distinct, signed, expiring storage capability; an M1 share
grant must not authorize fragment read/write/repair. On receive: stream to a
private temp file, bound size, verify expected ciphertext hash/length, fsync,
atomic rename, then persist a verified receipt. Never advertise healthy bytes
before durable commit.

Exit: 0 B, 1 B, 8 MiB-1, 8 MiB and 8 MiB+1 manifests; bounded-memory tests;
AEAD round trip, tamper and AAD substitution rejection; restart durability;
no plaintext fragment on disk; grant-scope negative tests. Map to M208-M210,
M222 and M227. Document key backup/recovery and the trusted-coordinator limit.

### M2.5 - Distribution matrix

Migrate desired fragment replica count separately from observed per-node
replica state. Track PLANNED, TRANSFERRING, HEALTHY, UNAVAILABLE, CORRUPT,
REMOVING, REMOVED and FAILED with verified receipt/time/hash. Derive file/Bay
health; offline is not LOST. Implement transactional compare-and-update and
copy->verify->commit->remove for any move. Add matrix/replica/health inspection
commands. Make reconciliation idempotent across restarts.

Exit: a planned or in-flight copy is never healthy; only durable verified
receipts promote it; outages/corruption change observed state without deleting
desired placement; restart/replay leaves a coherent matrix. Map to M212 and
part of M221-M222.

### M2.6 - Placement NBO v0

Implement initial and repair-destination placement on the M2.2 interface.
Hard-filter revoked/inactive, incompatible, full, unavailable, excluded and
already-hosting nodes before scoring. Version/configure weights for headroom,
availability, directional transfer quality, integrity evidence and diversity;
break ties by stable Node ID. Produce a persisted decision/plan before an
executor moves ciphertext. Never put two `STANDARD_2X` copies on one Node ID.

Exit: two eligible nodes yield two distinct verified placements; a high soft
score cannot override an exclusion; zero/one eligible-node cases remain
explicitly degraded or pending; ledger explains every candidate. Map to
M205, M211 and M213.

### M2.7 - DT-NBO v0

Select a healthy source, recipient, direct/relay route, bounded concurrency,
timeouts and fallback using directional BRG evidence and security policy.
Reuse M1 signed requests, relay admission, verified transport chunks, journals
and retry behavior. Write measured outcomes back to both NBO ledger and BRG.
Distinguish no healthy source, no route, authorization failure and checksum
failure. Never allow a score to downgrade a forced security policy.

Exit: source changes when a replica goes offline; A->B and B->A metrics are not
conflated; direct/relay outcomes stay separate; blocked-direct `auto` uses
secure relay with verified chunk reuse when available. Map to M214-M215.
Physical relay claims remain blocked by M1 C4/C5 until actually tested.

### M2.8 - Location-independent retrieval

Resolve a Bay file/version to its immutable manifest, choose a healthy source
for each fragment through DT-NBO, fetch ciphertext (possibly from different
nodes), verify ciphertext, decrypt only through authorized coordinator key
access, verify fragment plaintext and final size/SHA-256, then publish with
safe no-clobber export. Keep concurrency and buffers bounded; journal partial
retrieval for restart where feasible. The importer must have no special role
after verified two-copy commit.

Exit: source-independent retrieval with importer offline, fallback past a
corrupt/unavailable replica, multi-source reconstruction, matching final hash,
restart behavior and no-clobber. Map to M216-M220 and M228-M229. A two-node
physical demonstration is required for release, not just an integration test.

### M2.9 - Resilience NBO v0 and repair

Trigger evaluation on liveness, receipt/integrity failure, revocation and
periodic reconciliation. After configurable grace, compare desired/observed
healthy copies. Compose Placement NBO for destination and DT-NBO for source
and route, persist a repair plan, copy encrypted bytes, verify durable receipt,
then update matrix and outcomes. Never remove the last healthy copy. With only
two eligible nodes and one offline, report DEGRADED with `no eligible repair
target`; do not fabricate two copies on one node.

Exit: grace suppresses premature copying, three isolated Node IDs/state roots
complete automated repair, impossibility is explicit, restart/retry is safe,
revoked nodes are excluded. Map to M223-M226. Three physical devices are
recommended, not mandatory for the first two-host package gate.

## Cross-slice verification and release handoff

Use focused tests during each slice and the complete M1+M2 suite at integration
milestones. Before release, verify transactional `0.1.0a1` -> `0.2.0a1` state
migration on backups, M1 share usability, Windows/macOS CI and physical runs,
security denial/tamper cases, and the M201-M230 matrix. Build wheel/sdist,
run Ruff/pytest/coverage/Twine and content-level secret screening, then install
the local wheel cleanly. A planned `0.2.0a1` version is not an upload decision.

After M1 C3-C5 closure and owner authorization, use the TestPyPI-only plan for
upload, clean two-host provenance, 500 MiB physical Bay placement/retrieval,
client-isolated public-relay operation and resource measurements. Record all
results in `docs/M2_0_2_0a1_TESTPYPI_ACCEPTANCE.md`. Do not publish to production
PyPI. Capacity/Integrity NBOs, erasure coding, compute, AI, federation, BALL,
EDHE, economics and mobile agents remain out of scope.
