# M1 closure workspace

Status as of 2026-10-01: **NOT ACCEPTED**. This folder is an execution
checklist, not a new claim of test success. The authoritative requirement is
[M1_CLOSURE_AND_GATE.md](../M1_CLOSURE_AND_GATE.md); the current verdict lives
in [test-report.md](../test-report.md). Preserve dated historical evidence.
For each new run, use [the evidence template](EVIDENCE_TEMPLATE.md) in a new
dated report. Never overwrite a failed run with a later successful one.

## Gate board

| Gate | Current status | Evidence | What remains |
| --- | --- | --- | --- |
| C1 documentation reconciliation | PASS | [baseline](../M1_BASELINE_2026-09-30.md), [canonical report](../test-report.md) | Keep the verdict current as later evidence arrives. |
| C2 TestPyPI `0.1.0a1` provenance | PASS | [C2 record](../M1_C2_PROVENANCE_2026-10-01.md) | Preserve redacted logs; do not repeat solely for presentation. |
| C3 synchronized resources | RETEST REQUIRED | [C3 physical record](../M1_C3_RESOURCE_RESULTS_2026-10-01.md) | Rerun both directions using the same identified corrected artifact; prove no retained assemblies. |
| C4 public relay | NOT RUN | [closure specification](../M1_CLOSURE_AND_GATE.md) | Approved host/DNS/TLS and physical data/security/recovery matrix. |
| C5 isolated control path | LOCAL PASS / PHYSICAL NOT RUN | [C5 source record](../M1_C5_CONTROL_PATH_2026-10-01.md) | Physical client isolation, outbound-only control/data/revocation/outage/recovery. |

No public host, DNS name or valid TLS certificate has been approved yet.
Therefore C4/C5 are blocked on external infrastructure. Do not substitute a
localhost WSS test, accommodation Wi-Fi with direct coordinator reachability,
an unapproved tunnel, disabled certificate validation or port forwarding.

## Execution order and artifact control

1. Record Git SHA, dirty-state summary, OS/Python versions, package version,
   wheel and sdist SHA-256, installation source and exact test commands before
   changing test state. Freeze one candidate artifact for both physical hosts.
   The source cleanup/control changes are in an **unpublished** `0.1.0a2`
   candidate, not the published `0.1.0a1`. A source-tree test or a newly rebuilt
   wheel is not automatically the same candidate; record its new hash.
2. On a healthy Windows host, rerun the complete exact-source suite, including
   real-TLS/WSS integration, plus Ruff, build, Twine and artifact screening.
   The earlier 84-pass run exists, but a later exact-source run was not clean
   due to WSS timeouts and host memory exhaustion. Investigate repeat failures
   rather than relabeling them PASS. Run the same candidate's suite on macOS.
3. Install the identical corrected wheel into clean, dependency-complete
   environments on Mac and Windows, retain redacted installation logs, confirm
   `barn --version`, `pip check`, installed-file/wheel equivalence and SHA-256.
   Do not overwrite the `0.1.0a1` TestPyPI evidence or imply the correction
   candidate was fetched from TestPyPI if it was locally installed.
4. Back up private coordinator/node states and record backup verification
   before physical tests or upgrades. Keep keys, admin tokens, invites,
   package credentials and private state outside this repository. Use disposable
   test state for destructive revocation. Keep the Mac and Windows node IDs
   distinct and check certificate SANs against actual test URLs.
5. Execute C3 on the hotspot/direct network. Then, when owner-approved public
   relay infrastructure exists, execute C4 and C5. Record each attempt as
   PASS, FAIL, INCOMPLETE or NOT RUN with UTC start/end and exact artifact.
6. Review the final gate board against evidence. Only after every C1-C5 pass
   criterion below is met may the canonical report say M1 ACCEPTED. A human
   reviewer records name/UTC date and any residual non-blocking observation.

## C1 - documentation criterion

`docs/test-report.md` must be the single current verdict, with accurate PASS,
FAIL, INCOMPLETE and NOT RUN states. `docs/next-steps.md` must reflect the
current queue. Keep the September physical results and all dated checkpoints
unchanged as historical records; link later dated runs. C1 is already PASS,
but update the current verdict whenever C3-C5 change. Never quietly erase the
initial Windows-to-Mac direct failure or the retained-assembly discovery.

## C2 - installation provenance criterion

Mac and Windows each need fresh, isolated `0.1.0a1` installs from TestPyPI
with production-PyPI dependencies installed separately, a redacted source log,
downloaded-wheel SHA-256, installed-file comparison, `barn --version`,
`pip check` and coordinator/node smoke. The [C2 record](../M1_C2_PROVENANCE_2026-10-01.md)
documents PASS and its limits; do not conflate this with `0.1.0a2` corrected
artifact provenance or M2 release provenance.

## C3 - synchronized corrected-artifact resource rerun

Prerequisites: steps 1-4 above. Preserve the previous `0.1.0a1` run as FAIL
for its temp-file criterion. On the physical Mac/Windows pair:

1. Use fresh shares, transfer IDs and no-clobber output paths, plus a known
   deterministic 100 MiB source on **each** host. Record source size/SHA-256.
2. Start Mac->Windows and Windows->Mac direct HTTPS fetches within a narrow
   UTC window; show actual overlap from both start/end timestamps. Sample Mac
   coordinator and both node processes throughout for RSS/working set, free
   disk and node-state/transfer-journal size. Capture before, sampled minimum
   or peak, and after values, interval and sample count.
3. Record elapsed time, process IDs, direct transport, exit codes, destination
   size and full SHA-256 equality for both directions. Preserve any failed
   attempt and its logs; a successful retry is a separate observation.
4. Inspect both node `transfers/` trees after completed exports for retained
   `assembled.tmp` and publication temp files. Check bounded post-run state
   growth and no unexplained memory/disk accumulation. Retained verified M1
   chunks and managed copies are not, by themselves, the C3 defect.

C3 PASS requires a synchronized overlapping bidirectional 100 MiB run on the
same corrected artifact, matching hashes, recorded resource measurements and
no unbounded growth or retained completed-transfer temp files. If the direct
connection failure recurs, keep its timestamp/error and correlation evidence;
do not invent a cause or discard the failed attempt.

## C4 - approved public relay data-path test

Prerequisites: owner-controlled or explicitly approved public host, DNS,
valid TLS cert, outbound TCP 443 from both physical machines, and identical
tested package candidate on the endpoints. Deploy relay with only the public
coordinator grant key and relay TLS material. Verify its private runtime has
**no** Barn CA private key, node keys, coordinator admin token or private
coordinator state. Confirm bounded sessions, frames, bytes, timeouts and
redacted logs; verify `wss://` certificate/hostname validation is enabled.

On Mac and Windows, record distinct node identities, test endpoints and
connectivity. Then run and retain evidence for:

- forced relay 100 MiB Mac->Windows and Windows->Mac, with output size/hash;
- relay interruption and recovery, with resumable journal behavior;
- direct->relay `auto` fallback after blocking peer direct path, proving
  already verified transport chunks are reused rather than silently reset;
- share/node revocation denial and invalid/expired ticket, wrong peer and
  wrong Barn denial; no destination publication on denied operations;
- relay outage failing closed, followed by recovery after restart;
- relay visibility limited to opaque encrypted payload, with no file
  plaintext or key authority in its state/logs.

C4 PASS requires every item above on the deployed public relay, with real
Mac/Windows results and evidence. A local TLS relay test is useful regression
coverage but cannot close C4. Failures remain visible even if retried.

## C5 - client-isolated outbound control and data

Prerequisite: C4's approved public relay and the C5 corrected runtime. Set up
actual or enforced client isolation while **both** hosts retain outbound TCP
443 to the relay. Demonstrate with connection checks that Mac<->Windows direct
peer traffic is unavailable and the remote Windows node cannot reach Mac
coordinator HTTPS directly. Do not treat a merely unreliable LAN as isolation.
The Mac coordinator and both nodes must initiate outbound verified WSS/TLS;
no inbound cross-device route, TLS bypass, UPnP or unapproved tunnel is allowed.

While isolation is in force, prove and record:

1. Approved nodes maintain or restore coordinator control through the relay;
   signed/replay-protected requests and authenticated responses remain valid.
2. Heartbeat and registry update through fallback, followed by share creation,
   grant issuance and revocation. The relay has no admin or Barn authority.
3. A 100 MiB transfer completes through relay with matching SHA-256; revoked
   node and revoked share are denied without exposing file bytes.
4. Coordinator-control outage and relay outage produce distinguishable,
   fail-closed errors. Restoring each service restores allowed operations.

C5 PASS means required M1 control **and** data operations remain available
without direct cross-device LAN reachability. Source implementation plus local
tests do not satisfy the physical criterion.

## Final review and release boundary

For each gate, point to a dated report with exact artifact SHA, OS/versions,
topology, commands, UTC timestamps, positive and negative observations,
unexpected errors, measurements and reviewer. Update the current verdict only
after examining those records. M1 is accepted only if C1-C5 all PASS and no
blocking defect remains. Otherwise use BLOCKED/NOT ACCEPTED with the specific
missing criterion. M1 acceptance does not imply M2 storage acceptance, a
production PyPI release or that `0.1.0a1` acquired later fixes.

M2 design and code work may proceed while C4/C5 infrastructure is arranged,
but `0.2.0a1` TestPyPI release acceptance remains gated by the inherited
M1 network/security closure described here.
