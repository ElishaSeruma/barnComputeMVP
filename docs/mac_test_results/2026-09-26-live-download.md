# macOS live-download verification — 2026-09-26

## Scope

Verification of the live recipient-download checkpoint at commit
`5d5ac9bcddaf13f5d452847b528041a661b937ee` (`add live download
orchestration`). `barn share fetch` obtains a short-lived grant, retrieves the
manifest and fixed-size chunks over CA-verified HTTPS, persists each verified
chunk through the recipient journal, resumes completed chunks, and performs
final integrity-checked no-clobber export. Cancellation preserves the durable
journal for a later resume. Relay transport and richer cancellation/status
controls are out of scope.

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
| Full suite with `--cov=barn_compute --cov-report=term-missing` | PASS — 56 passed in 32.36s; 79% coverage |

The full suite emitted one known Starlette `TestClient` deprecation warning
concerning `httpx`. It did not affect assertions or the test outcome.

## Command

```sh
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  ./.venv-heartbeat-test/bin/python -m pytest -p pytest_cov -q \
  --cov=barn_compute --cov-report=term-missing
```

## Remaining checks

Relay transport, richer cancellation/status controls, package build,
`twine check`, archive screening, clean-wheel installation, and physical
two-node networking remain not run for this checkpoint.
