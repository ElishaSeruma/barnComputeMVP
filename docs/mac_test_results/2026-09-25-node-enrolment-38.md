# macOS node-enrolment checkpoint — 2026-09-25

Status: PASS

## Environment

- Git commit: `6cb8c815c2854e2814c41ededf1e00bf1b8cebea`
- macOS: 26.6 (build 25G5028f)
- Architecture: arm64
- Python: 3.12.14
- pip: 26.2.1
- Package version: 0.1.0a1

Fresh editable and clean-wheel virtual environments were used. The editable
import resolved to this checkout's `src/barn_compute` tree, and `pip check`
passed in both environments.

## Results

- Ruff: PASS.
- Full suite: PASS — 38 tests passed, 85% coverage.
- Focused enrolment and coordinator-service suite: PASS — 25 tests passed.
- Build: PASS — wheel and source distribution built.
- Twine: PASS for wheel and source distribution.
- Wheel inspection: PASS — includes `barn_compute/node/service.py`; no generated
  state, private keys, credentials, or host-specific data were present.
- Clean wheel installation and CLI smoke tests: PASS — `barn --version`, root,
  node, and coordinator help all worked.
- Disposable node initialization: PASS — initial status was `UNREGISTERED` and
  the state contained `node.json`, `node.csr.pem`, `secrets/identity-key.pem`,
  and `secrets/tls-key.pem`.
- Duplicate node initialization: PASS — returned `CONFIGURATION`, exit code 2,
  no traceback, and preserved the original Node ID.

## Local artifact hashes

- Wheel: `6bad221e509a057f8e08b35430144b0429d0e3ca7adbdb95b86deea7d346cc0d`
- Source distribution: `f0725b60d5e128edcf78f63afc4853a151d7d938b3eaac591432c4a2855cd8fa`

These are local macOS build hashes, not TestPyPI acceptance artifacts.

## Note

The first full test invocation stalled while reading stale Python bytecode
caches. Removing only regenerated `__pycache__` directories resolved that
environment issue; the full suite then passed without source or dependency
changes.

M1 remains `NOT YET RUN`: verified HTTPS services, heartbeats, file transfer,
relay behavior, TestPyPI provenance, and physical macOS-to-Windows acceptance
remain outstanding.
