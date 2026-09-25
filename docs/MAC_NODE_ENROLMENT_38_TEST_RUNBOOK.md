# Mac node-enrolment 38-test runbook

## Purpose

Verify the persistence-first node identity and explicit enrolment phase on the
Apple Silicon Mac. This is a testing and evidence task only. Do not add network
services, change dependencies, publish packages, or use real Barn state while
following this runbook.

Expected checkpoint:

- Package version: `0.1.0a1`
- Python: 3.11 or 3.12; use the installed Python 3.12
- Expected tests: exactly 38
- Expected Windows baseline: 38 passed, 85% coverage
- TestPyPI status: not published

## Safety rules

- Pull only into a clean checkout.
- Use fresh virtual environments and `mktemp` state.
- Do not use the normal per-user barnCompute state directory.
- Do not publish to TestPyPI or production PyPI.
- Do not paste invite codes, polling receipts, bearer tokens, or private keys
  into chat, commits, or reports.
- Do not mark physical two-machine or network acceptance as passed.
- Preserve exact failure output before making any code or dependency change.

## 1. Pull and record the exact source

```bash
cd ~/Desktop/barnComputeMVP
git status --short
git branch --show-current
git pull --ff-only

git rev-parse HEAD
sw_vers
uname -m
python3.12 --version
python3.12 -m pip --version
```

Expected branch: `main`. Expected architecture: `arm64`. Stop if local changes
would conflict with the pull.

## 2. Install into a fresh editable environment

```bash
python3.12 -m venv .venv-enrolment-test
PY="./.venv-enrolment-test/bin/python"

"$PY" -m pip install --upgrade pip
"$PY" -m pip install --verbose --editable '.[dev]'
"$PY" -m pip check
"$PY" -c 'import barn_compute; print(barn_compute.__file__); print(barn_compute.__version__)'
```

The import path must resolve to this checkout's `src/barn_compute` directory.
The version must be `0.1.0a1`.

## 3. Run the quality and enrolment gates

```bash
"$PY" -m ruff check .
"$PY" -m pytest -q --cov=barn_compute --cov-report=term-missing
```

Expected summary:

```text
All checks passed!
......................................                                   [100%]
38 passed
```

Record the actual coverage percentage. A small platform difference from the
Windows 85% baseline is acceptable when all 38 tests pass.

Also run the focused enrolment and migration tests:

```bash
"$PY" -m pytest -q \
  tests/unit/test_enrolment.py \
  tests/unit/test_coordinator_service.py
```

These tests cover:

- Two independent nodes remaining pending until explicit approval.
- Persistent Node IDs, separate identity/TLS keys, and SAN-bound CSRs.
- Out-of-band CA fingerprint pinning.
- Challenge binding, expiry, replay rejection, and receipt secrecy.
- Forged proof, malformed CSR, wrong SAN, wrong protocol, and conflicting key
  rejection.
- Explicit rejection and limited receipt polling.
- Idempotent transactional approval and invitation consumption.
- CA-signed Barn ID and grant-key certificate bindings.
- Node rejection of tampered bindings and untrusted CAs.
- Schema migration from the previous coordinator enrolment table.

If the suite does not collect exactly 38 tests, record:

```bash
git rev-parse HEAD
"$PY" -m pytest --collect-only -q
find tests -type f -name 'test_*.py' -print | sort
```

Do not report an older 18-test result as this checkpoint.

## 4. Build, validate, and inspect artifacts

```bash
"$PY" -m build
"$PY" -m twine check dist/*
"$PY" -m zipfile -l dist/barncompute-0.1.0a1-py3-none-any.whl
shasum -a 256 \
  dist/barncompute-0.1.0a1-py3-none-any.whl \
  dist/barncompute-0.1.0a1.tar.gz
```

Twine must report `PASSED` for both files. The wheel must include
`barn_compute/node/service.py` and must not include private keys, tokens,
certificates generated during tests, SQLite state, `.env`, virtual environments,
host paths, or user data.

The hashes are local Mac checkpoint hashes, not TestPyPI acceptance hashes.

## 5. Install the wheel in a second clean environment

```bash
python3.12 -m venv .venv-enrolment-wheel-test
PYW="./.venv-enrolment-wheel-test/bin/python"

"$PYW" -m pip install --upgrade pip
"$PYW" -m pip install ./dist/barncompute-0.1.0a1-py3-none-any.whl
"$PYW" -m pip check
./.venv-enrolment-wheel-test/bin/barn --version
./.venv-enrolment-wheel-test/bin/barn --help
./.venv-enrolment-wheel-test/bin/barn node --help
./.venv-enrolment-wheel-test/bin/barn coordinator --help
```

Expected version: `0.1.0a1`.

## 6. Exercise node initialization with disposable state

```bash
TEST_ROOT="$(mktemp -d)"
NODE_STATE="$TEST_ROOT/node"

./.venv-enrolment-wheel-test/bin/barn node init \
  --name MacNode \
  --advertise 127.0.0.1 \
  --peer-port 8445 \
  --state-dir "$NODE_STATE"
```

Verify the public metadata and expected filenames without printing private file
contents:

```bash
find "$NODE_STATE" -maxdepth 2 -type f -print | sort
"$PYW" -c 'import json,sys; p=json.load(open(sys.argv[1])); print(p["node_id"], p["status"], p["identity_fingerprint"])' "$NODE_STATE/node.json"
```

Expected initial files:

```text
node.csr.pem
node.json
secrets/identity-key.pem
secrets/tls-key.pem
```

Expected status: `UNREGISTERED`.

Confirm duplicate initialization fails cleanly without a traceback or overwrite:

```bash
./.venv-enrolment-wheel-test/bin/barn node init \
  --name ReplacementNode \
  --advertise 127.0.0.1 \
  --peer-port 8445 \
  --state-dir "$NODE_STATE"
echo "exit=$?"
```

Expected: safe `CONFIGURATION` message, exit code `2`, and no Python traceback.

`barn node enroll` remains intentionally unimplemented in this checkpoint. The
service-layer enrolment flow is tested locally; its real CLI operation requires
the next phase's verified HTTPS coordinator API. Do not report that as a test
failure.

## 7. Evidence to return

Return a concise report with:

```text
Git commit SHA:
macOS version/build:
Architecture:
Python version:
pip version:
Editable import path:
Ruff result:
Full pytest count/result:
Coverage:
Focused enrolment test result:
Build result:
Twine wheel result:
Twine sdist result:
Wheel SHA-256:
Sdist SHA-256:
Clean-wheel install and pip check:
CLI version/help result:
Node init result:
Initial node status:
Duplicate-init exit/message/no-traceback result:
Unexpected warnings or failures:
```

Do not include invitation codes, receipts, tokens, private key material, or
sensitive host paths.

## 8. Pass criteria

Mark the Mac node-enrolment checkpoint `PASS` only if:

- The checkout is on the intended `main` commit.
- Editable import resolves to this checkout.
- Ruff passes.
- Exactly 38 tests pass.
- Focused enrolment and migration tests pass.
- Wheel and sdist build successfully and pass Twine.
- Wheel contents contain no generated secrets or state.
- A clean environment installs and runs the wheel.
- Disposable `barn node init` creates the expected state.
- Duplicate node initialization returns exit code 2 without a traceback and
  does not alter the existing Node ID.

Otherwise mark it `FAIL` and return exact failing commands and output. Even a
passing result leaves overall M1 at `NOT YET RUN`: HTTPS enrolment, heartbeats,
file transfers, relay operation, TestPyPI provenance, and physical two-machine
acceptance remain outstanding.

