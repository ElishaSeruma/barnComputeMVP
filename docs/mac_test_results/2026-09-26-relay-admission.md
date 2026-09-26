# macOS relay-admission verification — 2026-09-26

## Scope

Verification of the signed relay-admission checkpoint at commit
`2d7f7125ca379eba7ca8525786704e07254e9e7c` (`implement relay admission`).
Coordinators issue five-minute Barn-scoped tickets; the relay validates the
grant-key signature, expiry, and peer membership before admitting a WSS
connection. Opaque frames are bounded to 1 MiB and routed only to the ticket's
peer; the relay has no file-grant authority. Inner authenticated/encrypted peer
sessions, production relay deployment, ticket retrieval surfaces, and physical
failover are out of scope.

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
| Full suite with `--cov=barn_compute --cov-report=term-missing` | PASS — 61 passed in 4.00s; 79% coverage |

The full suite emitted one known Starlette `TestClient` deprecation warning
concerning `httpx`. It did not affect assertions or the test outcome.

## Command

```sh
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  ./.venv-heartbeat-test/bin/python -m pytest -p pytest_cov -q \
  --cov=barn_compute --cov-report=term-missing
```

## Remaining checks

Inner authenticated/encrypted peer sessions, production relay deployment,
ticket retrieval surfaces, physical relay failover, package build, `twine check`,
archive screening, clean-wheel installation, and physical two-node networking
remain not run for this checkpoint.
