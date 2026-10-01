# M1 closure run evidence template

Copy this content into a new dated report in this folder for each run. Replace
placeholders; leave unrun checks as NOT RUN. Do not include secrets, private
state, raw tokens, invitation codes or private-key paths in shared output.

## Identity and environment

- Gate and scenario: `<C3 | C4 | C5 / description>`
- Verdict: `PASS | FAIL | INCOMPLETE | NOT RUN`
- UTC start/end: `<timestamps>`
- Git SHA and dirty-state summary: `<value>`
- Package/version and source: `<local wheel | TestPyPI URL>`
- Wheel SHA-256 (same on both hosts?): `<value>`
- Mac OS/arch/Python/pip: `<values>`
- Windows OS/arch/Python/pip: `<values>`
- Relay host approval/DNS/TLS identity (public details only): `<values>`
- Coordinator/Barn/Node IDs and public CA fingerprint: `<values>`
- Network topology and verified allowed/blocked paths: `<values>`
- Backup verification and disposable-state note: `<values>`

## Execution

| Check | UTC start/end | Command or method | Expected | Observed | Status | Evidence path |
| --- | --- | --- | --- | --- | --- | --- |
| `<check>` | `<timestamps>` | `<redacted>` | `<expected>` | `<observed>` | `PASS/FAIL/NOT RUN` | `<path>` |

For transfers record source/destination byte count and SHA-256, share and
transfer IDs, transport, elapsed time, journal reuse, exit code and any retry.
For C3 include sample interval/count and before/minimum-or-peak/after RSS,
free disk, node-state and transfer-journal size on both hosts. For C4/C5 include
ticket/grant denials, isolation proof, outage errors and recovery. Identify
failed attempts separately from successful retries.

## Review

- Unexpected errors and retained failure logs: `<details>`
- Secret/log/archive screening: `<result>`
- Missing evidence or limitations: `<details>`
- Exact pass criterion met or not met: `<reason>`
- Next action: `<action>`
- Human reviewer and UTC review date: `<value>`
- Canonical `docs/test-report.md` updated: `YES | NO`
