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
  development dependencies.
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
| Full suite with `--cov=barn_compute --cov-report=term-missing` | NOT COMPLETED — stopped during Python module filesystem reads before collection/output |
| Build, Twine, clean-wheel install, and physical two-node checks | NOT RUN for this commit |

Both passing test commands emitted the known Starlette `TestClient` deprecation
warning concerning the `httpx` import; it did not affect the assertions.

## Full-suite limitation and rerun

Initial Python imports in this checkout intermittently blocked on bytecode
cache writes. Disabling bytecode writes allowed package imports and both focused
test groups to pass. The full coverage process subsequently remained in kernel
`read` calls while importing modules for several minutes and produced no test
collection or result output. A one-second `sample` capture showed Python inside
module import file reads, not an application test failure. The process was
stopped, so the 47-test/81%-coverage macOS gate is **not yet claimed as passed**.

After the local filesystem contention is clear, rerun:

```sh
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  ./.venv-heartbeat-test/bin/python -m pytest -p pytest_cov -q \
  --cov=barn_compute --cov-report=term-missing
```

Then run the package build, `twine check`, archive screening, and clean-wheel
installation before promoting this checkpoint to PASS.
