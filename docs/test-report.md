# barnCompute M1 TestPyPI acceptance report

Release candidate: 0.1.0a1
Distribution index: TestPyPI (https://test.pypi.org/simple/)
TestPyPI release page: NOT PUBLISHED
Wheel file/SHA-256: earlier macOS local wheel `69d8d2c6ffb8e3ef779bdd358b2f5dda47b048f271b3e6a600e2a34c081717e3`; earlier macOS local sdist `d959e6b40969882ed0fb5eb532a8b11810a3799409b090e137effe317afcb351`; coordinator-foundation macOS checkpoint (2026-09-25) wheel `390c3084745cd48daacbbfe1b2c36120153709ba585bfc5bc55d179e90beab04`; coordinator-bootstrap runbook checkpoint at `8c03b346282269ef645acb549ddc7b7586faa514` (2026-09-25) sdist `1164df43aba1fcd88f3407d7dd13ab4bf324abb34443db881ae195c58f500fe8`; none is a TestPyPI acceptance artifact
macOS version/architecture/Python/pip: macOS 26.6 (build 25G5028f), arm64 (Apple Silicon), Python 3.12.14, pip 26.2.1; fresh environments `.venv-coordinator-test` and `.venv-coordinator-wheel-test`
Windows version/architecture/Python/pip: local foundation checks passed on Python 3.12.10; exact Windows, architecture, and pip versions NOT RECORDED
Coordinator and Node IDs: disposable coordinator initialization and public-CA export PASS; matching fingerprints, CA without private-key material, and duplicate-initialization rejection PASS; ephemeral coordinator ID not retained; node initialization NOT RUN
Installation provenance on each host: NOT RUN
Automated unit/integration/security/packaging: Windows node-enrolment service checkpoint PASS on 2026-09-25 with Python 3.12.10: Ruff PASS; 38 tests PASS with 85% coverage; wheel/sdist build and Twine PASS. Coverage includes durable node identity, separate TLS CSR key, pinned CA, challenge and receipt secrecy, proof/CSR/SAN validation, pending approval, explicit rejection, idempotent approval, certificate and grant-key binding, restart persistence, schema migration, and negative cases for expiry, replay, malformed CSR, forged proof, conflicting identity, consumed invite, wrong node, wrong protocol, untrusted CA, and tampered grant binding. macOS coordinator-bootstrap checkpoint remains PASS at 18 tests and 84% coverage; the expanded 38-test node-enrolment checkpoint is NOT RUN on macOS. Network integration and full M1 security suites NOT RUN
Physical matrix F01-F24: NOT RUN
SHA-256 Mac-to-Windows: NOT RUN
SHA-256 Windows-to-Mac: NOT RUN
Measured resume behaviour, memory, network failures: NOT RUN
Known issues and blocking defects: enrolment network/admin APIs and node agent runtime, heartbeat, file transfer, and relay implementation incomplete
Release verdict: NOT YET RUN
Human reviewer and UTC date: NOT RUN
