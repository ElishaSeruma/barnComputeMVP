# macOS grant-authenticated peer-delivery verification — 2026-09-26

## Scope

Verification of the grant-authenticated peer-delivery checkpoint at commit
`9f786cb6b766494e7d91500a64d4c32705f2f6fc` (`implement grant authenticated
peer delivery`). Approved source nodes expose grant-validated manifest and
fixed-chunk endpoints through their existing Barn-CA HTTPS listener. The slice
checks grant signatures and expiry, source/file scope, manifest ownership,
chunk bounds, and per-chunk SHA-256 integrity. Durable transfer sessions,
recipient-side journals, resume, final assembly, share HTTP/CLI surfaces, and
relay transport are out of scope.

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
| Full suite with `--cov=barn_compute --cov-report=term-missing` | PASS — 53 passed in 3.64s; 80% coverage |

The full suite emitted one known Starlette `TestClient` deprecation warning
concerning `httpx`. It did not affect assertions or the test outcome.

## Command

```sh
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  ./.venv-heartbeat-test/bin/python -m pytest -p pytest_cov -q \
  --cov=barn_compute --cov-report=term-missing
```

## Remaining checks

Durable transfer sessions, recipient-side journals, resume, final assembly,
share HTTP/CLI surfaces, relay transport, package build, `twine check`, archive
screening, clean-wheel installation, and physical two-node networking remain
not run for this checkpoint.
