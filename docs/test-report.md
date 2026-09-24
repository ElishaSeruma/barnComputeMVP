# barnCompute M1 TestPyPI acceptance report

Release candidate: 0.1.0a1
Distribution index: TestPyPI (https://test.pypi.org/simple/)
TestPyPI release page: NOT PUBLISHED
Wheel file/SHA-256: macOS local wheel `69d8d2c6ffb8e3ef779bdd358b2f5dda47b048f271b3e6a600e2a34c081717e3`; macOS local sdist `d959e6b40969882ed0fb5eb532a8b11810a3799409b090e137effe317afcb351`; neither is the TestPyPI acceptance artifact
macOS version/architecture/Python/pip: macOS on Apple Silicon, Python 3.12.14; exact macOS and pip versions NOT RECORDED
Windows version/architecture/Python/pip: local foundation checks passed on Python 3.12.10; exact Windows, architecture, and pip versions NOT RECORDED
Coordinator and Node IDs: NOT RUN
Installation provenance on each host: NOT RUN
Automated unit/integration/security/packaging: Windows coordinator-foundation checks PASS with 18 tests and 84% coverage on Python 3.12.10; macOS earlier foundation checkpoint PASS with 12 tests and 84% coverage on Python 3.12.14; the expanded coordinator suite has not yet run on macOS; `ruff check .`, `pytest -q --cov=barn_compute`, `python -m build`, and `twine check dist/*` passed at the recorded checkpoints; integration and full security suites NOT RUN
Physical matrix F01-F24: NOT RUN
SHA-256 Mac-to-Windows: NOT RUN
SHA-256 Windows-to-Mac: NOT RUN
Measured resume behaviour, memory, network failures: NOT RUN
Known issues and blocking defects: coordinator, node agent, file transfer, and relay implementation incomplete
Release verdict: NOT YET RUN
Human reviewer and UTC date: NOT RUN
