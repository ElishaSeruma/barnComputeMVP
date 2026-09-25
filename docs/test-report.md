# barnCompute M1 TestPyPI acceptance report

Release candidate: 0.1.0a1
Distribution index: TestPyPI (https://test.pypi.org/simple/)
TestPyPI release page: NOT PUBLISHED
Wheel file/SHA-256: earlier macOS local wheel `69d8d2c6ffb8e3ef779bdd358b2f5dda47b048f271b3e6a600e2a34c081717e3`; earlier macOS local sdist `d959e6b40969882ed0fb5eb532a8b11810a3799409b090e137effe317afcb351`; coordinator-bootstrap macOS wheel `390c3084745cd48daacbbfe1b2c36120153709ba585bfc5bc55d179e90beab04`; coordinator-bootstrap macOS sdist `1164df43aba1fcd88f3407d7dd13ab4bf324abb34443db881ae195c58f500fe8`; node-enrolment macOS checkpoint at `6cb8c815c2854e2814c41ededf1e00bf1b8cebea` wheel `6bad221e509a057f8e08b35430144b0429d0e3ca7adbdb95b86deea7d346cc0d` and sdist `f0725b60d5e128edcf78f63afc4853a151d7d938b3eaac591432c4a2855cd8fa`; none is a TestPyPI acceptance artifact
macOS version/architecture/Python/pip: macOS 26.6 (build 25G5028f), arm64 (Apple Silicon), Python 3.12.14, pip 26.2.1; fresh node-enrolment environments `.venv-enrolment-test` and `.venv-enrolment-wheel-test`; detailed evidence in `docs/mac_test_results/2026-09-25-node-enrolment-38.md`
Windows version/architecture/Python/pip: local foundation checks passed on Python 3.12.10; exact Windows, architecture, and pip versions NOT RECORDED
Coordinator and Node IDs: disposable coordinator initialization and public-CA export PASS; matching fingerprints, CA without private-key material, and duplicate-initialization rejection PASS. macOS node-enrolment checkpoint PASS: disposable node initialization produced `UNREGISTERED` state and expected files; duplicate node initialization returned `CONFIGURATION`, exit code 2, no traceback, and preserved the Node ID.
Installation provenance on each host: NOT RUN
Automated unit/integration/security/packaging: Windows node-enrolment service checkpoint PASS on 2026-09-25 with Python 3.12.10: Ruff PASS; 38 tests PASS with 85% coverage; wheel/sdist build and Twine PASS. macOS node-enrolment checkpoint PASS on 2026-09-25 at `6cb8c815c2854e2814c41ededf1e00bf1b8cebea`: Ruff PASS; full suite PASS (38 tests, 85% coverage); focused enrolment/coordinator-service suite PASS (25 tests); wheel/sdist build, Twine, clean-wheel installation, CLI smoke tests, disposable node initialization, and duplicate-init safety checks PASS. The first test invocation stalled on stale Python bytecode; after regenerating only `__pycache__` directories, the suite passed without source or dependency changes. Network integration and full M1 security suites NOT RUN
Physical matrix F01-F24: NOT RUN
SHA-256 Mac-to-Windows: NOT RUN
SHA-256 Windows-to-Mac: NOT RUN
Measured resume behaviour, memory, network failures: NOT RUN
Known issues and blocking defects: enrolment network/admin APIs and node agent runtime, heartbeat, file transfer, and relay implementation incomplete
Release verdict: NOT YET RUN
Human reviewer and UTC date: NOT RUN
