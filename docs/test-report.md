# barnCompute M1 TestPyPI acceptance report

Release candidate: 0.1.0a1  
Distribution index: TestPyPI (https://test.pypi.org/simple/)  
TestPyPI release page: NOT PUBLISHED  
Wheel file/SHA-256: locally built; not the TestPyPI acceptance artifact  
macOS version/architecture/Python/pip: NOT RUN  
Windows version/architecture/Python/pip: NOT RUN  
Coordinator and Node IDs: NOT RUN  
Installation provenance on each host: NOT RUN  
Automated unit/integration/security/packaging: 12 foundation unit tests PASS on Windows with Python 3.12.10; `ruff check .`, `pytest -q --cov=barn_compute`, `python -m build`, and `twine check dist/*` PASS; integration and full security suites NOT RUN  
Physical matrix F01-F24: NOT RUN  
SHA-256 Mac-to-Windows: NOT RUN  
SHA-256 Windows-to-Mac: NOT RUN  
Measured resume behaviour, memory, network failures: NOT RUN  
Known issues and blocking defects: coordinator, node agent, file transfer, and relay implementation incomplete  
Release verdict: NOT YET RUN  
Human reviewer and UTC date: NOT RUN
