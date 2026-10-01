# barnCompute M1 TestPyPI acceptance report

## Current verdict - 2026-10-01

**M1 NOT ACCEPTED: closure gates C3-C5 remain open.** C1 and C2 pass. This section is the
canonical current status. Checkpoints below the historical divider describe
their own dates and do not override this verdict.

Release: `barnCompute==0.1.0a1`, published to
[TestPyPI](https://test.pypi.org/project/barnCompute/0.1.0a1/).
Publication and artifact details are recorded in the
[physical handoff](M1_PHYSICAL_TEST_HANDOFF_2026-09-29.md) and
[physical results](M1_PHYSICAL_TEST_RESULTS_2026-09-29.md); publication was not
independently rechecked online during this documentation reconciliation.

- Published wheel SHA-256: `f1cbc28f916749b15cc46a2e5ab7760ad27d9693153c76e36ec2d070f85acd86`.
- Published sdist SHA-256: `ab32556fa838cb3ed886d77f409a3edefd39550a0ec0f6cfa3c847087378c8b9`.
- The September 29 environments matched 30 checked wheel entries, excluding
  `RECORD`; that established content equivalence only. Fresh October 1 installs
  now establish retained installation provenance on both hosts (see C2 below).
- Documentation baseline: `415786816a1b6087e2b86d947be4957e27ab99fe`.

### Evidence matrix

PASS means the cited check passed; FAIL means an observed failed check;
INCOMPLETE means some required evidence exists but the gate is unmet;
NOT RUN means the required acceptance scenario has no recorded run.

| Check | Status | Evidence and limits |
| --- | --- | --- |
| TestPyPI publication | PASS | Published hashes recorded in the dated handoff and physical results. |
| Installed package content, both hosts | PASS | Same published wheel matched installed files; original installer logs absent. |
| Clean TestPyPI installation provenance | PASS | [2026-10-01 C2 run](M1_C2_PROVENANCE_2026-10-01.md): both hosts have fresh installs, retained source logs, matching wheel/content, `pip check`, version and HTTPS smoke. Mac evidence is owner-shared terminal output; its logs remain on that host. |
| Windows local automation | PASS | [Fresh baseline](M1_BASELINE_2026-09-30.md) at `4157868`: Ruff, 82 tests, no failures/skips, 82% coverage, 500.87 seconds; build, Twine and existing archive screen passed. [Historical Windows verification](WINDOWS_M1_RUNTIME_VERIFICATION.md) retained. |
| macOS local automation | PASS (historical) | [Mac verification](mac_test_results/2026-09-26-integrated-m1-acceptance-local.md): 82 passed, 82% coverage at `842bc31`; packaging and clean-wheel checks passed. No fresh Mac run claimed. |
| Physical trust, enrolment and connectivity | PASS | CA fingerprint agreement, explicit approval, ONLINE registry and peer TCP checks in physical results. Mac pending-list output was not captured. |
| Physical direct 100 MiB, both directions | PASS | Matching full SHA-256; Windows-to-Mac succeeded after an initial failed attempt. |
| Initial Windows-to-Mac attempt | FAIL (retry passed) | `CONFIGURATION: Direct peer connection failed`; root cause not established. Retain as a known observation. |
| Boundary files and no-clobber | PASS | 0 B, 1 B, 1 MiB and 1 MiB+1 B; existing destination preserved. |
| Recovery and cancellation | PASS | Missing/corrupt chunk repair, interrupted transfer across coordinator/agent restart, incomplete-transfer cancellation/resume. Chunk timestamps support saved-chunk reuse; peer request logs were not retained. |
| Physical authorization denials | PASS | Expired, revoked and wrong-recipient shares; disposable node revocation. |
| Concurrent physical direct transfers | PASS | Overlapping bidirectional 100 MiB transfers with matching hashes. |
| Synchronized resource observations | RETEST REQUIRED | [2026-10-01 C3 run](M1_C3_RESOURCE_RESULTS_2026-10-01.md): synchronized bidirectional retry passed with matching hashes and bounded sampled memory, but each completed transfer retained a 100 MiB `assembled.tmp`. Source fix and corrected-artifact physical rerun required. |
| Deployed public relay acceptance | NOT RUN | Forced relay, failover/resume, outage/recovery, ticket/peer denial and relay revocation evidence still required. |
| Client-isolated control/data fallback | LOCAL PASS / PHYSICAL NOT RUN | [C5 implementation record](M1_C5_CONTROL_PATH_2026-10-01.md): outbound authenticated control, existing signed/replay-checked RPC and local isolation/outage/recovery tests pass in unpublished `0.1.0a2`; public two-device test remains. |

The full physical evidence, including timestamps, identifiers, hashes and
measurement limitations, remains unchanged in
[M1_PHYSICAL_TEST_RESULTS_2026-09-29.md](M1_PHYSICAL_TEST_RESULTS_2026-09-29.md).

### Closure gates

| Gate | Status | Exact remaining work |
| --- | --- | --- |
| C1 - reconcile documentation | PASS | Current report and next steps reconcile publication and physical evidence while retaining dated records. |
| C2 - installation provenance | PASS | Windows and Mac passed on 2026-10-01; see the dated C2 record for scope and retained evidence. |
| C3 - synchronized resources | RETEST REQUIRED | Physical measurements completed, exposing unbounded retained assembly files. Verify the cleanup fix with a newly identified artifact and repeat the synchronized run. |
| C4 - public relay | NOT RUN | Approved host, DNS and verified TLS on 443; complete physical relay/security/recovery matrix. |
| C5 - isolated-network control path | INCOMPLETE (source implemented) | Local authenticated outbound control tests pass in `0.1.0a2`; prove control and data operations physically with all cross-device LAN paths unavailable. |

See [the closure specification](M1_CLOSURE_AND_GATE.md) for full pass conditions
and [the current baseline record](M1_BASELINE_2026-09-30.md) for this slice's
source inspection and fresh check results. No physical gate was rerun here.
Any code correction needs its own tested artifact identity; the published
`0.1.0a1` must not be overwritten or credited with later behavior.

M2 development may proceed alongside closure work. Its inherited network/security
gates must pass before `0.2.0a1` publication/acceptance under the new plan.
Human acceptance review remains pending.

## Historical checkpoints (superseded status, preserved evidence)

The text below is retained for traceability. Claims such as NOT PUBLISHED,
physical NOT RUN, or pending Mac reruns describe earlier checkpoints only.

Release candidate: 0.1.0a1
Distribution index: TestPyPI (https://test.pypi.org/simple/)
TestPyPI release page: NOT PUBLISHED
Wheel file/SHA-256: earlier macOS local wheel `69d8d2c6ffb8e3ef779bdd358b2f5dda47b048f271b3e6a600e2a34c081717e3`; earlier macOS local sdist `d959e6b40969882ed0fb5eb532a8b11810a3799409b090e137effe317afcb351`; coordinator-bootstrap macOS wheel `390c3084745cd48daacbbfe1b2c36120153709ba585bfc5bc55d179e90beab04`; coordinator-bootstrap macOS sdist `1164df43aba1fcd88f3407d7dd13ab4bf324abb34443db881ae195c58f500fe8`; node-enrolment macOS checkpoint wheel `6bad221e509a057f8e08b35430144b0429d0e3ca7adbdb95b86deea7d346cc0d` and sdist `f0725b60d5e128edcf78f63afc4853a151d7d938b3eaac591432c4a2855cd8fa`; HTTPS/admin macOS checkpoint at `fa13622` wheel `60a14cdea34851c3b83dc72519de9cbbd958cdb8211a157d1fc1fdbdebea81d1` and sdist `d14757b25236330ffbe483b0cabdaaaa8f2baf92b207727917db63eae5b50357`; none is a TestPyPI acceptance artifact
macOS version/architecture/Python/pip: macOS 26.6 (build 25G5028f), arm64 (Apple Silicon), Python 3.12.14, pip 26.2.1; detailed evidence in `docs/mac_test_results/2026-09-25-node-enrolment-38.md`, `docs/mac_test_results/2026-09-25-https-admin-43.md`, `docs/mac_test_results/2026-09-26-heartbeat-registry.md`, `docs/mac_test_results/2026-09-26-managed-file-import.md`, `docs/mac_test_results/2026-09-26-share-grants.md`, `docs/mac_test_results/2026-09-26-peer-delivery.md`, `docs/mac_test_results/2026-09-26-transfer-journals.md`, `docs/mac_test_results/2026-09-26-share-control-plane.md`, `docs/mac_test_results/2026-09-26-live-download.md`, `docs/mac_test_results/2026-09-26-relay-policy.md`, `docs/mac_test_results/2026-09-26-relay-admission.md`, `docs/mac_test_results/2026-09-26-inner-session-failure.md`, `docs/mac_test_results/2026-09-26-inner-session-ticket-retrieval.md`, and `docs/mac_test_results/2026-09-26-identity-bound-handshake.md`
Windows version/architecture/Python/pip: local foundation checks passed on Python 3.12.10; exact Windows, architecture, and pip versions NOT RECORDED
Coordinator and Node IDs: disposable coordinator initialization and public-CA export PASS; matching fingerprints, CA without private-key material, and duplicate-initialization rejection PASS. macOS node-enrolment checkpoint PASS: disposable node initialization produced `UNREGISTERED` state and expected files; duplicate node initialization returned `CONFIGURATION`, exit code 2, no traceback, and preserved the Node ID.
Installation provenance on each host: NOT RUN
Automated unit/integration/security/packaging: Windows HTTPS/admin implementation checkpoint PASS on 2026-09-25 with Python 3.12.10: Ruff PASS; 43 tests PASS with 82% coverage. The signed heartbeat/registry checkpoint PASS on 2026-09-26 with Python 3.12.10: Ruff PASS; 47 tests PASS with 81% coverage. The immutable managed-file import checkpoint PASS on 2026-09-26 with Python 3.12.10: Ruff PASS; 50 tests PASS with 80% coverage. The suite covers private staged imports, fixed 1 MiB manifests, zero-byte files, size limits, manifest persistence, signed heartbeats, nonce and sequence replay boundaries, liveness transitions, registry refresh, and exact-body HTTP verification. macOS HTTPS/admin checkpoint PASS on 2026-09-25 at `fa13622`: Ruff PASS; full suite PASS (43 tests, 82% coverage); focused HTTP/client suite PASS (5 tests); wheel/sdist build and Twine PASS. macOS heartbeat/registry checkpoint PASS on 2026-09-26 in a fresh local `/Users/elisha/Developer/barnComputeMVP` environment: pytest import PASS (pytest 8.4.2); Ruff PASS; full suite PASS (47 tests in 4.22s, 81% coverage); heartbeat integration PASS (4 tests); transport/heartbeat focus PASS (9 tests). macOS managed-file import checkpoint PASS on 2026-09-26 at `4b8b844`: pytest import PASS (pytest 8.4.2); Ruff PASS; full suite PASS (50 tests in 5.70s, 80% coverage). The earlier Desktop checkout's Python module filesystem-read delay was resolved by running from the local Developer checkout; detailed evidence is in `docs/mac_test_results/2026-09-26-heartbeat-registry.md` and `docs/mac_test_results/2026-09-26-managed-file-import.md`. A generated coverage artifact was initially found in the source distribution; generalizing the coverage ignore rule to `.coverage*` and rebuilding removed it. The known Starlette TestClient deprecation warning was observed. Physical network integration and full M1 security suites NOT RUN
Physical matrix F01-F24: NOT RUN
SHA-256 Mac-to-Windows: NOT RUN
SHA-256 Windows-to-Mac: NOT RUN
Measured resume behaviour, memory, network failures: NOT RUN
Known issues and blocking defects: final Mac rerun, public relay deployment, physical two-host acceptance, and TestPyPI provenance remain outstanding. Live coordinator HTTPS reachability is required during direct and relay delivery.
Release verdict: NOT YET RUN
Human reviewer and UTC date: NOT RUN

Share/grant authority checkpoint: Windows PASS on 2026-09-26 with Ruff PASS,
52 tests PASS, and 80% coverage. macOS PASS at `4b084e5` on 2026-09-26:
pytest import PASS (pytest 8.4.2); Ruff PASS; full suite PASS (52 tests in
3.72s, 80% coverage). Coverage includes durable recipient-scoped shares,
expiry, revocation, recipient binding, and signed five-minute transfer grants.
Detailed macOS evidence is in `docs/mac_test_results/2026-09-26-share-grants.md`.
Peer transfer and relay behavior remain NOT RUN.

Peer delivery checkpoint: Windows PASS on 2026-09-26 with Ruff PASS, 53 tests
PASS, and 80% coverage. macOS PASS at `9f786cb` on 2026-09-26: pytest import
PASS (pytest 8.4.2); Ruff PASS; full suite PASS (53 tests in 3.64s, 80%
coverage). Coverage includes grant-authenticated manifest and fixed-chunk
routes, grant signature and expiry checks, source/file scope checks, and chunk
integrity validation. Detailed macOS evidence is in
`docs/mac_test_results/2026-09-26-peer-delivery.md`. Durable transfer sessions,
resume, and relay behavior remain NOT RUN.

Transfer journal checkpoint: Windows PASS on 2026-09-26 with Ruff PASS, 54
tests PASS, and 80% coverage. macOS PASS at `596f17a` on 2026-09-26: pytest
import PASS (pytest 8.4.2); Ruff PASS; full suite PASS (54 tests in 3.56s, 80%
coverage). Coverage includes durable recipient journals, verified chunk
persistence, restart reuse, full-file assembly and SHA-256 verification, and
no-clobber export. Detailed macOS evidence is in
`docs/mac_test_results/2026-09-26-transfer-journals.md`. Live download
orchestration, cancellation, and relay behavior remain NOT RUN.

Share control-plane checkpoint: Windows PASS on 2026-09-26 with Ruff PASS, 55
tests PASS, and 79% coverage. macOS PASS at `63bb325` on 2026-09-26: pytest
import PASS (pytest 8.4.2); Ruff PASS; full suite PASS (55 tests in 3.60s, 80%
coverage). Coverage includes authenticated loopback share creation, listing,
revocation, and signed transfer-grant issuance. Detailed macOS evidence is in
`docs/mac_test_results/2026-09-26-share-control-plane.md`. Live download
orchestration, cancellation, and relay behavior remain NOT RUN.

Live download checkpoint: Windows PASS on 2026-09-26 with Ruff PASS, 56 tests
PASS, and 79% coverage. macOS PASS at `5d5ac9b` on 2026-09-26: pytest import
PASS (pytest 8.4.2); Ruff PASS; full suite PASS (56 tests in 32.36s, 79%
coverage). Coverage includes grant retrieval, CA-verified peer manifest/chunk
orchestration, journal-backed resume, final integrity, and no-clobber export.
Detailed macOS evidence is in `docs/mac_test_results/2026-09-26-live-download.md`.
Relay behavior remains NOT RUN.

Relay policy checkpoint: Windows PASS on 2026-09-26 with Ruff PASS, 60 tests
PASS, and 79% coverage. macOS PASS at `084c2a9` on 2026-09-26: pytest import
PASS (pytest 8.4.2); Ruff PASS; full suite PASS (60 tests in 3.73s, 79%
coverage). Coverage includes fail-closed `direct`, `relay`, and `auto`
selection plus direct-to-relay fallback rules. Detailed macOS evidence is in
`docs/mac_test_results/2026-09-26-relay-policy.md`. A deployed WSS relay,
admission protocol, inner protected session, and physical relay failover remain
NOT RUN.

Relay admission checkpoint: Windows PASS on 2026-09-26 with Ruff PASS, 61 tests
PASS, and 79% coverage. macOS PASS at `2d7f712` on 2026-09-26: pytest import
PASS (pytest 8.4.2); Ruff PASS; full suite PASS (61 tests in 4.00s, 79%
coverage). Coverage includes signed five-minute ticket issuance, WSS admission
validation, peer scoping, opaque 1 MiB frame bounds, and relay failure behavior.
Detailed macOS evidence is in `docs/mac_test_results/2026-09-26-relay-admission.md`.
Inner protected sessions, production deployment, ticket retrieval surfaces, and
physical failover remain NOT RUN.

Inner session and ticket retrieval checkpoint: Windows PASS on 2026-09-26 with
Ruff PASS; full suite PASS (62 tests, 79% coverage). macOS initially failed at
`d1c4148` because the admin route passed the relay-ticket TTL positionally;
the route was corrected to match the service's keyword-only signature. The
corrected local rerun at `e8dbda7` passed Ruff and the full suite (62 tests in
4.14s, 80% coverage). The original failure is recorded in
`docs/mac_test_results/2026-09-26-inner-session-failure.md`; successful rerun
evidence is in `docs/mac_test_results/2026-09-26-inner-session-ticket-retrieval.md`.
Coverage includes
the authenticated relay-ticket retrieval endpoint and X25519/HKDF/
ChaCha20-Poly1305 envelope round-trip with associated-data rejection. The
session handshake is not yet bound to node certificate identity, and physical
relay failover remains NOT RUN.

Identity-bound inner handshake checkpoint: Windows PASS on 2026-09-26 with
Ruff PASS and 63 tests PASS. macOS PASS at `8f5df27` on 2026-09-26: pytest
import PASS (pytest 8.4.2); Ruff PASS; full suite PASS (63 tests in 4.26s, 80%
coverage). Session hellos sign the node UUID, ephemeral X25519 public key, and
transcript with the enrolled Ed25519 identity; forged identity and transcript
cases are rejected. Detailed macOS evidence is in
`docs/mac_test_results/2026-09-26-identity-bound-handshake.md`.

## Integrated runtime checkpoint - 2026-09-26

Windows source suite: 82 PASS, no skips, 343.01 seconds, 82% source coverage.
Independent installed-wheel suite: 81 PASS, one initial symlink skip, 348.11
seconds, 82% coverage. The Windows junction fallback subsequently passed in
the complete source suite. A final config-error redaction adjustment passed
both focused config tests after those full runs.

Ruff, wheel/sdist build, Twine validation, archive screening and clean-wheel
import/CLI checks passed. Real local TLS/WSS integration covers 100 MiB direct
and relay transfers in both logical directions, matching SHA-256, resumed
chunks, automatic failover, signed recipient/relay authentication and revocation.
Additional coverage includes durable audit, cancellation, managed copies,
concurrent no-clobber export and listener shutdown.

Full evidence: `WINDOWS_M1_RUNTIME_VERIFICATION.md`. Mac rerun and deployment
instructions: `M1_ACCEPTANCE_RUNBOOK.md` and
`mac_instructions/2026-09-26-integrated-m1.md`.

macOS local verification PASS at `842bc31` on 2026-09-26: fresh Python 3.12.14
environment; Ruff PASS; full local HTTPS/WSS suite PASS (82 tests in 61.56s,
82% coverage); wheel/sdist build PASS; Twine and archive screening PASS; and
clean-wheel import/CLI checks PASS. Artifact SHA-256 values and detailed
evidence are in `docs/mac_test_results/2026-09-26-integrated-m1-acceptance-local.md`.

Public relay, physical two-host resource measurements, and TestPyPI installation
provenance remain NOT RUN. Historical checkpoint gaps above are superseded by
this runtime checkpoint, not evidence of physical acceptance. Release verdict
remains NOT YET RUN; M1 is not accepted until those external gates pass.
