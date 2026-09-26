# macOS fail-closed transport-policy verification — 2026-09-26

## Scope

Verification of the fail-closed transport-policy checkpoint at commit
`084c2a90c52c8fb486ad9cb4499137833616695f` (`add fail closed transport
policy`). `direct`, `relay`, and `auto` modes now have explicit selection
rules: `auto` prefers direct HTTPS and falls back only to a configured relay;
forced modes fail closed. The separately deployed WSS relay service, admission
tickets, inner protected peer sessions, and physical relay failover are out of
scope.

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
| Full suite with `--cov=barn_compute --cov-report=term-missing` | PASS — 60 passed in 3.73s; 79% coverage |

The full suite emitted one known Starlette `TestClient` deprecation warning
concerning `httpx`. It did not affect assertions or the test outcome.

## Command

```sh
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  ./.venv-heartbeat-test/bin/python -m pytest -p pytest_cov -q \
  --cov=barn_compute --cov-report=term-missing
```

## Remaining checks

The separately deployed WSS relay service, admission protocol, inner protected
peer sessions, physical direct-to-relay failover, package build, `twine check`,
archive screening, clean-wheel installation, and physical two-node networking
remain not run for this checkpoint.
