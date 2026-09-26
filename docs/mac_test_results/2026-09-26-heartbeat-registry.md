# macOS heartbeat and registry verification — 2026-09-26

## Scope

Verification of the signed heartbeat and registry checkpoint at commit
`93600dfe6b71731fad941487f09f0af180131dfc` (`implement signed heartbeat
registry`). The Windows checkpoint reports 47 tests and 81% coverage; this
record is the corresponding Apple Silicon evidence.

## Environment

- macOS 26.6 (build 25G5028f), Apple Silicon (`arm64`).
- Python 3.12.14.
- Fresh local `.venv-heartbeat-test` virtual environment with the project
  development dependencies, created in the local
  `/Users/elisha/Developer/barnComputeMVP` checkout (outside iCloud-managed
  Desktop/Documents storage).
- Tests used `PYTHONPATH=src`, `PYTHONDONTWRITEBYTECODE=1`, and
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` (with `-p pytest_cov` for coverage) to
  avoid a local bytecode-cache/filesystem-read issue. These are test-runner
  settings only; no project source was changed.

## Results

| Check | Result |
| --- | --- |
| `ruff check src tests` | PASS — all checks passed |
| `pytest -q tests/integration/test_heartbeat_registry.py` | PASS — 4 passed in 13.69s |
| `pytest -q tests/integration/test_http_enrolment.py tests/integration/test_heartbeat_registry.py tests/test_http_clients.py` | PASS — 9 passed in 8.15s |
| Full suite with `--cov=barn_compute --cov-report=term-missing` | PASS — 47 passed in 4.22s; 81% coverage |
| Build, Twine, clean-wheel install, and physical two-node checks | NOT RUN for this commit |

Both passing test commands emitted the known Starlette `TestClient` deprecation
warning concerning the `httpx` import; it did not affect the assertions.

## Full-suite rerun

The initial Desktop-based checkout intermittently blocked during Python module
filesystem reads before collection. Moving the checkout to local
`/Users/elisha/Developer` and creating a fresh Python 3.12.14 environment
resolved the issue. The import check printed pytest `8.4.2`, and the rerun
completed successfully:

```sh
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  ./.venv-heartbeat-test/bin/python -m pytest -p pytest_cov -q \
  --cov=barn_compute --cov-report=term-missing
```

The full suite reported **47 passed, 1 warning in 4.22s** with **81%** total
coverage. Ruff also passed in the fresh environment. The warning is the known
Starlette `TestClient` deprecation concerning `httpx`; it did not affect test
assertions. The package build, `twine check`, archive screening, clean-wheel
installation, and physical two-node checks remain outstanding.
