# macOS durable transfer-journal verification — 2026-09-26

## Scope

Verification of the durable recipient-side transfer checkpoint at commit
`596f17a107b276dfc0f57ccfb75fe9d9b257f10d` (`implement durable transfer
journals`). The slice persists journals after every verified fixed-size chunk,
reuses completed chunks after restart, assembles only complete manifests,
verifies final size and SHA-256, and exports through a no-clobber destination
operation. Share HTTP/CLI surfaces, live download orchestration, cancellation,
and relay transport are out of scope.

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
| Full suite with `--cov=barn_compute --cov-report=term-missing` | PASS — 54 passed in 3.56s; 80% coverage |

The full suite emitted one known Starlette `TestClient` deprecation warning
concerning `httpx`. It did not affect assertions or the test outcome.

## Command

```sh
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  ./.venv-heartbeat-test/bin/python -m pytest -p pytest_cov -q \
  --cov=barn_compute --cov-report=term-missing
```

## Remaining checks

Share HTTP/CLI surfaces, live download orchestration, cancellation, relay
transport, package build, `twine check`, archive screening, clean-wheel
installation, and physical two-node networking remain not run for this
checkpoint.
