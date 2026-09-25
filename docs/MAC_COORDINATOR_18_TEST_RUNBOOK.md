# Mac coordinator-bootstrap 18-test runbook

## Purpose

Run and document the expanded `barnCompute` coordinator-bootstrap checkpoint on
the Apple Silicon Mac. This is a verification task only. Do not implement new
features, publish packages, use real coordinator state, or change dependency
versions while following this runbook.

The expected checkpoint contains 18 tests covering the package foundation,
signed-request authentication, replay protection, private key persistence,
coordinator initialization, certificate generation, public CA export, and
hashed expiring invitations.

## Expected repository state

- Repository: `barnComputeMVP`
- Branch: `main`
- Python: 3.11 or 3.12; prefer the existing Python 3.12 installation
- Package version: `0.1.0a1`
- TestPyPI status: not published
- Expected test count: 18

Before testing, read:

- `README.md`
- `docs/architecture.md`
- `docs/protocol-v1.md`
- `docs/next-steps.md`
- `docs/test-report.md`

## Safety constraints

- Use only a fresh local virtual environment and disposable coordinator state.
- Do not use or modify a real user state directory.
- Do not paste real invite codes, tokens, or private keys into chat or logs.
- Do not run any Twine upload command.
- Do not publish to TestPyPI or production PyPI.
- Do not mark physical macOS/Windows acceptance as passed.
- Do not change source code merely to force a test to pass. Preserve exact
  failure output and diagnose it first.
- The generated invitation in this runbook is disposable, but redact it from
  any public report.

## 1. Update and identify the checkout

Open Terminal and enter the repository:

```bash
cd ~/Desktop/barnComputeMVP
git status --short
git branch --show-current
git log -5 --oneline
git pull --ff-only
```

Record:

```bash
git rev-parse HEAD
sw_vers
uname -m
python3.12 --version
python3.12 -m pip --version
```

Expected architecture is normally `arm64`. Stop and report before pulling if
`git status --short` shows local source or documentation changes that would be
overwritten or conflict with the remote branch.

## 2. Create a fresh test environment

Use a new environment name so an older editable installation cannot interfere:

```bash
python3.12 -m venv .venv-coordinator-test
PY="./.venv-coordinator-test/bin/python"

"$PY" -m pip install --upgrade pip
"$PY" -m pip install --verbose --editable '.[dev]'
```

The option order is important: `--verbose` appears before `--editable`.

Confirm the installed source and version:

```bash
"$PY" -c 'import barn_compute; print(barn_compute.__file__); print(barn_compute.__version__)'
"$PY" -m pip check
./.venv-coordinator-test/bin/barn --version
```

Expected version:

```text
0.1.0a1
```

`barn_compute.__file__` must point into this repository's `src/barn_compute`
tree. `pip check` should report no broken requirements.

## 3. Run lint and the 18-test suite

```bash
"$PY" -m ruff check .
"$PY" -m pytest -q --cov=barn_compute --cov-report=term-missing
```

Expected results:

```text
All checks passed!
..................                                                       [100%]
18 passed
```

The previous Windows checkpoint measured 84% total coverage. Small
platform-specific coverage differences are acceptable if all 18 tests pass;
record the actual Mac percentage rather than editing it to match Windows.

If the test count is not 18, run:

```bash
git rev-parse HEAD
find tests -type f -name 'test_*.py' -print | sort
"$PY" -m pytest --collect-only -q
```

Report the output. Do not label a 12-test result as the expanded coordinator
checkpoint.

## 4. Build and validate package artifacts

```bash
"$PY" -m build
"$PY" -m twine check dist/*
```

Expected artifacts:

```text
dist/barncompute-0.1.0a1-py3-none-any.whl
dist/barncompute-0.1.0a1.tar.gz
```

Expected Twine result for both files: `PASSED`.

Inspect the wheel and record hashes:

```bash
"$PY" -m zipfile -l dist/barncompute-0.1.0a1-py3-none-any.whl
shasum -a 256 \
  dist/barncompute-0.1.0a1-py3-none-any.whl \
  dist/barncompute-0.1.0a1.tar.gz
```

The wheel may contain package modules, package metadata, the `barn` entry point,
README metadata, and the Apache license. It must not contain `.env` files,
private keys, tokens, certificates created during tests, SQLite databases,
virtual environments, test state, host-specific paths, or user files.

These new hashes describe a local Mac build. They are not TestPyPI acceptance
hashes and do not need to match earlier local builds.

## 5. Test the built wheel in a clean environment

Create a second environment to ensure the non-editable wheel installs and runs:

```bash
python3.12 -m venv .venv-coordinator-wheel-test
PYW="./.venv-coordinator-wheel-test/bin/python"

"$PYW" -m pip install --upgrade pip
"$PYW" -m pip install ./dist/barncompute-0.1.0a1-py3-none-any.whl
"$PYW" -m pip check
./.venv-coordinator-wheel-test/bin/barn --version
./.venv-coordinator-wheel-test/bin/barn --help
./.venv-coordinator-wheel-test/bin/barn doctor --json
```

Expected version is `0.1.0a1`. `doctor` currently reports an incomplete system;
that is expected because node enrolment and network services are not yet
implemented.

## 6. Exercise coordinator bootstrap with disposable state

Use the CLI installed from the wheel:

```bash
TEST_ROOT="$(mktemp -d)"
COORDINATOR_STATE="$TEST_ROOT/coordinator"
EXPORTED_CA="$TEST_ROOT/barn-ca.pem"

./.venv-coordinator-wheel-test/bin/barn coordinator init \
  --name LabBarn \
  --advertise 127.0.0.1 \
  --state-dir "$COORDINATOR_STATE"

./.venv-coordinator-wheel-test/bin/barn coordinator ca export \
  --output "$EXPORTED_CA" \
  --state-dir "$COORDINATOR_STATE"

./.venv-coordinator-wheel-test/bin/barn coordinator invite \
  --ttl 10m \
  --state-dir "$COORDINATOR_STATE"
```

Verify:

- `init` prints a Barn ID and CA SHA-256 fingerprint.
- `ca export` prints the same CA fingerprint.
- The public CA file exists and contains `BEGIN CERTIFICATE`, never `PRIVATE
  KEY`.
- `invite` prints an ID, one-use code, and UTC expiry.
- Repeating `coordinator init` against the same state directory fails safely
  instead of overwriting it.

Commands:

```bash
test -f "$EXPORTED_CA"
grep 'BEGIN CERTIFICATE' "$EXPORTED_CA"
if grep -q 'PRIVATE KEY' "$EXPORTED_CA"; then
  echo 'FAIL: exported CA contains private key material'
  exit 1
fi

./.venv-coordinator-wheel-test/bin/barn coordinator init \
  --name ReplacementBarn \
  --advertise 127.0.0.1 \
  --state-dir "$COORDINATOR_STATE"
```

The final command is expected to exit nonzero with a message that coordinator
state already exists.

Do not display or inspect files under `$COORDINATOR_STATE/secrets` beyond
confirming their names and existence:

```bash
find "$COORDINATOR_STATE" -maxdepth 2 -type f -print | sort
```

Expected files include:

```text
ca-cert.pem
coordinator-cert.pem
coordinator.db
coordinator.json
secrets/admin.token
secrets/ca-key.pem
secrets/coordinator-key.pem
secrets/grant-key.pem
```

## 7. Evidence to return

Return one report containing:

```text
Git commit SHA:
macOS version:
Architecture:
Python version:
pip version:
Editable import path:
Ruff result:
Pytest result and count:
Coverage percentage:
Build result:
Twine wheel result:
Twine sdist result:
Wheel SHA-256:
Sdist SHA-256:
Clean-wheel installation result:
CLI version result:
Coordinator init result:
Init CA fingerprint:
Export CA fingerprint:
Duplicate-init rejection result:
Unexpected warnings or failures:
```

Redact the invitation code, bearer tokens, local usernames when sharing
publicly, and any sensitive absolute paths. Barn IDs and certificate
fingerprints are not secrets, but may still be omitted from a public report.

## 8. Pass criteria

Mark this Mac coordinator-bootstrap checkpoint `PASS` only when all of the
following are true:

- Checkout is on the intended `main` commit.
- Editable import resolves to this checkout.
- Ruff passes.
- Exactly 18 tests pass.
- Wheel and sdist build successfully.
- Twine validates both artifacts.
- A clean environment installs and runs the built wheel.
- Coordinator initialization succeeds in disposable state.
- Exported CA fingerprint matches the initialization fingerprint.
- Exported CA contains no private key.
- Duplicate initialization is rejected without changing existing state.

Otherwise mark it `FAIL` and include exact commands and output. This checkpoint
does not change the overall M1 verdict from `NOT YET RUN`, because node
enrolment, transfers, relay behavior, TestPyPI provenance, and physical
cross-platform acceptance remain outstanding.

