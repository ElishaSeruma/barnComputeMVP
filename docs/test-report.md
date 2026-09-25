# barnCompute M1 TestPyPI acceptance report

Release candidate: 0.1.0a1
Distribution index: TestPyPI (https://test.pypi.org/simple/)
TestPyPI release page: NOT PUBLISHED
Wheel file/SHA-256: earlier macOS local wheel `69d8d2c6ffb8e3ef779bdd358b2f5dda47b048f271b3e6a600e2a34c081717e3`; earlier macOS local sdist `d959e6b40969882ed0fb5eb532a8b11810a3799409b090e137effe317afcb351`; coordinator-foundation macOS checkpoint (2026-09-25) wheel `390c3084745cd48daacbbfe1b2c36120153709ba585bfc5bc55d179e90beab04`; coordinator-foundation macOS checkpoint (2026-09-25) sdist `3f8dd9ab7b5966087ce352915cb89ebaf4e96dcb6c2bf93b2ebd6abb0a05bb44`; none is a TestPyPI acceptance artifact
macOS version/architecture/Python/pip: macOS 26.6 (build 25G5028f), arm64 (Apple Silicon), Python 3.12.14, pip 26.2.1; clean environment `.venv-mac-test`
Windows version/architecture/Python/pip: local foundation checks passed on Python 3.12.10; exact Windows, architecture, and pip versions NOT RECORDED
Coordinator and Node IDs: disposable coordinator initialization PASS (ephemeral coordinator ID not retained); node initialization NOT RUN
Installation provenance on each host: NOT RUN
Automated unit/integration/security/packaging: Windows coordinator-bootstrap checks reverified on 2026-09-25 with 18 tests passing and 84% coverage on Python 3.12.10; Ruff, wheel/sdist build, and `twine check dist/*` PASS. macOS coordinator-foundation checkpoint PASS on 2026-09-25 with Python 3.12.14: `ruff check .` PASS, `pytest -q --cov=barn_compute` PASS (18 tests, 84% coverage), `python -m build` PASS, `twine check dist/*` PASS, `pip check` PASS, and `barn --version`/`barn --help` PASS. Disposable coordinator initialization, public-CA export, one-use invitation creation, and CA fingerprint matching PASS. Integration and full security suites NOT RUN
Physical matrix F01-F24: NOT RUN
SHA-256 Mac-to-Windows: NOT RUN
SHA-256 Windows-to-Mac: NOT RUN
Measured resume behaviour, memory, network failures: NOT RUN
Known issues and blocking defects: coordinator network/admin services, node enrolment and agent, file transfer, and relay implementation incomplete
Release verdict: NOT YET RUN
Human reviewer and UTC date: NOT RUN
