# macOS managed-file import verification — 2026-09-26

## Scope

Verification of the immutable managed-file import checkpoint at commit
`4b8b844f057121dfd286bb650975d9b83d4f7f7b` (`implement managed file import`).
This checkpoint adds private UUID-addressed storage, atomic staged imports,
fixed 1 MiB chunk manifests, whole-file and per-chunk SHA-256 hashes,
zero-byte file support, size and free-space checks, manifest validation, and
`barn file add` / `barn file list` commands. Shares, peer serving, transfer
sessions, resume journals, and relay transport are out of scope.

## Environment

- macOS 26.6 (build 25G5028f), Apple Silicon (`arm64`).
- Python 3.12.14; pytest 8.4.2.
- Fresh local `.venv-heartbeat-test` environment with project development
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
| Full suite with `--cov=barn_compute --cov-report=term-missing` | PASS — 50 passed in 5.70s; 80% coverage |

The full suite emitted one known Starlette `TestClient` deprecation warning
concerning `httpx`. It did not affect assertions or the test outcome.

## Command

```sh
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  ./.venv-heartbeat-test/bin/python -m pytest -p pytest_cov -q \
  --cov=barn_compute --cov-report=term-missing
```

## Remaining checks

Build, `twine check`, archive screening, clean-wheel installation, physical
two-node networking, shares, transfer sessions, and relay verification remain
not run for this checkpoint.
