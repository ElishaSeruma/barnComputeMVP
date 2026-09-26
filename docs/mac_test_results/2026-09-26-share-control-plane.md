# macOS share control-plane verification — 2026-09-26

## Scope

Verification of the share control-plane checkpoint at commit
`63bb3257ecb1c69342a894449dec1075a4845794` (`add share control plane`). The
loopback admin API and CLI support authenticated share creation, listing,
revocation, and signed transfer-grant issuance. Live download orchestration,
cancellation, and relay transport are out of scope.

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
| Full suite with `--cov=barn_compute --cov-report=term-missing` | PASS — 55 passed in 3.60s; 80% coverage |

The full suite emitted one known Starlette `TestClient` deprecation warning
concerning `httpx`. It did not affect assertions or the test outcome. The
macOS coverage result is one percentage point above the documented Windows
checkpoint result (79%).

## Command

```sh
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  ./.venv-heartbeat-test/bin/python -m pytest -p pytest_cov -q \
  --cov=barn_compute --cov-report=term-missing
```

## Remaining checks

Live download orchestration, cancellation, relay transport, package build,
`twine check`, archive screening, clean-wheel installation, and physical
two-node networking remain not run for this checkpoint.
