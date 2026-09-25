# macOS HTTPS and loopback-admin checkpoint

Run this after pulling the commit that contains this document. These commands
use a fresh environment and do not modify existing Barn state.

## 1. Prepare

```bash
cd ~/Desktop/barnComputeMVP
git pull --ff-only
git rev-parse HEAD
rm -rf .venv-https-test build dist
python3.12 -m venv .venv-https-test
PY="./.venv-https-test/bin/python"
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -e '.[dev]'
```

The install can spend several minutes at `Installing build dependencies` on a
cold network. For verbose output, put `-v` before the editable option:

```bash
"$PY" -m pip install -v -e '.[dev]'
```

## 2. Run quality and behavior checks

```bash
"$PY" -m ruff check .
"$PY" -m pytest -q --cov=barn_compute --cov-report=term-missing
"$PY" -m pytest -q tests/integration/test_http_enrolment.py tests/test_http_clients.py
```

Expected result: Ruff passes, the complete suite reports **43 passed**, and the
focused HTTP/client suite reports **5 passed**. A Starlette deprecation warning
about TestClient/httpx is currently known and is not a test failure.

## 3. Build and inspect distributions

```bash
"$PY" -m build
"$PY" -m twine check dist/*
unzip -l dist/barncompute-0.1.0a1-py3-none-any.whl
tar -tzf dist/barncompute-0.1.0a1.tar.gz
shasum -a 256 dist/barncompute-0.1.0a1-py3-none-any.whl dist/barncompute-0.1.0a1.tar.gz
```

Both Twine checks must pass. Confirm no private keys, admin tokens, local state,
`.env` files, or test caches appear in either archive.

## 4. Record evidence

Create `docs/mac_test_results/2026-09-25-https-admin-43.md` containing:

- tested commit hash;
- `sw_vers`, `uname -m`, `python3.12 --version`, and pip version;
- Ruff, complete-suite, and focused-suite outcomes;
- coverage total;
- build and Twine outcomes;
- both SHA-256 hashes;
- package-content inspection outcome;
- every warning, failure, workaround, or unexpected delay.

Do not mark physical Mac-to-Windows networking, TestPyPI provenance, heartbeat,
file transfer, or relay tests as passed. Those remain `NOT RUN` at this gate.
