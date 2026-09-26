# barnCompute M1 TestPyPI acceptance report

Release candidate: 0.1.0a1
Distribution index: TestPyPI (https://test.pypi.org/simple/)
TestPyPI release page: NOT PUBLISHED
Wheel file/SHA-256: earlier macOS local wheel `69d8d2c6ffb8e3ef779bdd358b2f5dda47b048f271b3e6a600e2a34c081717e3`; earlier macOS local sdist `d959e6b40969882ed0fb5eb532a8b11810a3799409b090e137effe317afcb351`; coordinator-bootstrap macOS wheel `390c3084745cd48daacbbfe1b2c36120153709ba585bfc5bc55d179e90beab04`; coordinator-bootstrap macOS sdist `1164df43aba1fcd88f3407d7dd13ab4bf324abb34443db881ae195c58f500fe8`; node-enrolment macOS checkpoint wheel `6bad221e509a057f8e08b35430144b0429d0e3ca7adbdb95b86deea7d346cc0d` and sdist `f0725b60d5e128edcf78f63afc4853a151d7d938b3eaac591432c4a2855cd8fa`; HTTPS/admin macOS checkpoint at `fa13622` wheel `60a14cdea34851c3b83dc72519de9cbbd958cdb8211a157d1fc1fdbdebea81d1` and sdist `d14757b25236330ffbe483b0cabdaaaa8f2baf92b207727917db63eae5b50357`; none is a TestPyPI acceptance artifact
macOS version/architecture/Python/pip: macOS 26.6 (build 25G5028f), arm64 (Apple Silicon), Python 3.12.14, pip 26.2.1; detailed evidence in `docs/mac_test_results/2026-09-25-node-enrolment-38.md`, `docs/mac_test_results/2026-09-25-https-admin-43.md`, `docs/mac_test_results/2026-09-26-heartbeat-registry.md`, `docs/mac_test_results/2026-09-26-managed-file-import.md`, and `docs/mac_test_results/2026-09-26-share-grants.md`
Windows version/architecture/Python/pip: local foundation checks passed on Python 3.12.10; exact Windows, architecture, and pip versions NOT RECORDED
Coordinator and Node IDs: disposable coordinator initialization and public-CA export PASS; matching fingerprints, CA without private-key material, and duplicate-initialization rejection PASS. macOS node-enrolment checkpoint PASS: disposable node initialization produced `UNREGISTERED` state and expected files; duplicate node initialization returned `CONFIGURATION`, exit code 2, no traceback, and preserved the Node ID.
Installation provenance on each host: NOT RUN
Automated unit/integration/security/packaging: Windows HTTPS/admin implementation checkpoint PASS on 2026-09-25 with Python 3.12.10: Ruff PASS; 43 tests PASS with 82% coverage. The signed heartbeat/registry checkpoint PASS on 2026-09-26 with Python 3.12.10: Ruff PASS; 47 tests PASS with 81% coverage. The immutable managed-file import checkpoint PASS on 2026-09-26 with Python 3.12.10: Ruff PASS; 50 tests PASS with 80% coverage. The suite covers private staged imports, fixed 1 MiB manifests, zero-byte files, size limits, manifest persistence, signed heartbeats, nonce and sequence replay boundaries, liveness transitions, registry refresh, and exact-body HTTP verification. macOS HTTPS/admin checkpoint PASS on 2026-09-25 at `fa13622`: Ruff PASS; full suite PASS (43 tests, 82% coverage); focused HTTP/client suite PASS (5 tests); wheel/sdist build and Twine PASS. macOS heartbeat/registry checkpoint PASS on 2026-09-26 in a fresh local `/Users/elisha/Developer/barnComputeMVP` environment: pytest import PASS (pytest 8.4.2); Ruff PASS; full suite PASS (47 tests in 4.22s, 81% coverage); heartbeat integration PASS (4 tests); transport/heartbeat focus PASS (9 tests). macOS managed-file import checkpoint PASS on 2026-09-26 at `4b8b844`: pytest import PASS (pytest 8.4.2); Ruff PASS; full suite PASS (50 tests in 5.70s, 80% coverage). The earlier Desktop checkout's Python module filesystem-read delay was resolved by running from the local Developer checkout; detailed evidence is in `docs/mac_test_results/2026-09-26-heartbeat-registry.md` and `docs/mac_test_results/2026-09-26-managed-file-import.md`. A generated coverage artifact was initially found in the source distribution; generalizing the coverage ignore rule to `.coverage*` and rebuilding removed it. The known Starlette TestClient deprecation warning was observed. Physical network integration and full M1 security suites NOT RUN
Physical matrix F01-F24: NOT RUN
SHA-256 Mac-to-Windows: NOT RUN
SHA-256 Windows-to-Mac: NOT RUN
Measured resume behaviour, memory, network failures: NOT RUN
Known issues and blocking defects: peer file transfer, share HTTP/CLI surfaces, and relay implementation remain incomplete; physical network integration and full M1 security verification remain outstanding
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
PASS, and 80% coverage. Coverage includes grant-authenticated manifest and
fixed-chunk routes, grant signature and expiry checks, source/file scope checks,
and chunk integrity validation. Durable transfer sessions, resume, and relay
behavior remain NOT RUN.
