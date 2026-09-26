# macOS share and transfer-grant verification — 2026-09-26

## Scope

Verification of the recipient-scoped share and transfer-grant authority
checkpoint at commit `4b084e5d6e30d9d47e815fa85d607a84edd137a0`
(`implement recipient share grants`). The checkpoint covers durable shares,
approved-node authorization, one-second-to-30-day expiry, revocation,
recipient binding, five-minute transfer grants, and Ed25519 signatures over
the complete grant scope. Peer HTTPS serving, share HTTP/CLI surfaces, chunk
transfer, resume journals, and relay transport are not included.

## Environment

- macOS 26.6 (build 25G5028f), Apple Silicon (`arm64`).
- Python 3.12.14; pytest 8.4.2.
- Local `.venv-heartbeat-test` environment with project development
  dependencies in `/Users/elisha/Developer/barnComputeMVP`, outside
  iCloud-managed Desktop/Documents storage.
- Commands used `PYTHONPATH=src`, `PYTHONDONTWRITEBYTECODE=1`, and
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`; coverage was enabled with
  `-p pytest_cov`.

## Results

| Check | Result |
| --- | --- |
| Pytest import check | PASS — pytest 8.4.2 printed successfully |
| `ruff check src tests` | PASS — all checks passed |
| Full suite with `--cov=barn_compute --cov-report=term-missing` | PASS — 52 passed in 3.72s; 80% coverage |

The full suite emitted one known Starlette `TestClient` deprecation warning
concerning `httpx`. It did not affect assertions or the test outcome.

## Command

```sh
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  ./.venv-heartbeat-test/bin/python -m pytest -p pytest_cov -q \
  --cov=barn_compute --cov-report=term-missing
```

## Remaining checks

Peer HTTPS serving, share HTTP/CLI surfaces, chunk transfer, resume journals,
relay transport, package build, `twine check`, archive screening, clean-wheel
installation, and physical two-node networking remain not run for this
checkpoint.
