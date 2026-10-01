# START HERE — barnCompute M1 Closure + M2 (0.2.0a1)

## Purpose

Continue the existing `barnComputeMVP` repository. Do **not** restart the architecture, replace the M1 trust model, or treat M2 as a new standalone application.

Read these repository documents before changing code:

- `README.md`
- `docs/architecture.md`
- `docs/protocol-v1.md`
- `docs/M1_ACCEPTANCE_RUNBOOK.md`
- `docs/M1_PHYSICAL_TEST_RESULTS_2026-09-29.md`
- `docs/test-report.md`
- `docs/next-steps.md`

Then read, in this package:

1. `M1_CLOSURE_AND_GATE.md`
2. `BRG_AND_NBO_V0_SPEC.md`
3. `M2_1_TO_M2_9_IMPLEMENTATION_SPEC.md`
4. `TESTPYPI_0_2_0A1_ACCEPTANCE_PLAN.md`

## Current baseline

`barnCompute==0.1.0a1` already implements the M1 runtime: Barn identity, node enrolment and approval, node identity persistence, signed/replay-resistant requests, heartbeats, immutable managed-file import, recipient-specific shares, grant-authenticated direct HTTPS transfer, resumable 1 MiB transport chunks, cancellation/resume, corruption repair, WSS relay transport, encrypted identity-bound inner relay sessions, and `direct | relay | auto` transport policy.

Physical Mac↔Windows direct transfer evidence exists, including 100 MiB transfers, restart/resume, cancellation/resume, missing/corrupt chunk repair, revocation, boundary files, and concurrent transfers. M1 is **not yet accepted** because closure gates remain.

## Strict implementation order

### Closure track

Complete the M1 closure work in `M1_CLOSURE_AND_GATE.md`. M2 design and implementation can proceed in a feature branch while external relay/provenance tests are being arranged, but:

- do not mark M1 accepted early;
- do not delete or rewrite M1 test evidence;
- do not publish `0.2.0a1` until M1 closure blockers that affect the inherited network/security substrate are resolved.

### M2 track

Implement only M2.1 through M2.9:

- M2.1 — Barn Resource Graph (BRG) v0
- M2.2 — NBO framework and decision/outcome ledger
- M2.3 — Bay model
- M2.4 — storage fragments and encrypted replicas
- M2.5 — distribution matrix
- M2.6 — Placement NBO v0
- M2.7 — DT-NBO v0
- M2.8 — location-independent retrieval
- M2.9 — Resilience NBO v0 and repair

Explicitly defer Capacity NBO, Integrity/Scrub NBO, compute scheduling, AI inference, multi-Barn federation, erasure coding, BALL, EDHE, economics, mobile agents, and production PyPI.

## Architectural rule

From M2 onward, storage decisions follow:

```text
BRG state
   ↓
NBO decision
   ↓
immutable decision record
   ↓
planner
   ↓
M1/M2 executor
   ↓
measured outcome
   ↓
BRG observation + NBO outcome
```

No M2 placement, transfer-source selection, or repair destination may bypass the NBO interface merely because the first version uses deterministic rules.

NBOs **decide**. Executors **perform side effects**.

## Compatibility rules

- Preserve M1 package name: `barnCompute`
- Preserve import name: `barn_compute`
- Preserve CLI: `barn`
- Preserve existing M1 functionality and state.
- `0.2.0a1` is a package version, not automatically a wire-protocol-major change.
- Prefer backward-compatible protocol extensions and explicit feature negotiation.
- Existing `0.1.0a1` coordinator/node state must migrate transactionally; never wipe state implicitly.
- Existing M1 managed files and shares must remain readable/operable after migration.
- Existing M1 1 MiB chunks remain **transport chunks**, not M2 storage fragments.

## Release rule

The first M2 distribution candidate is:

`barnCompute==0.2.0a1`

It is published to **TestPyPI only** after the specified automated, migration, security and package gates pass. Production PyPI is out of scope.

## Codex completion report

At the end of each implementation slice, report:

- Git commit SHA
- files changed
- migrations added
- commands run
- tests passed/failed/not run
- coverage
- compatibility impact
- security impact
- new CLI/API surfaces
- known limitations
- exact next gate

Do not claim physical, relay, TestPyPI, or cross-platform success without actual evidence.
