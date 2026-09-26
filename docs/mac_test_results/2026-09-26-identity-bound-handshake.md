# macOS identity-bound inner-handshake verification — 2026-09-26

## Scope

Verification of the identity-bound inner-handshake checkpoint at commit
`8f5df274a8e80b471ef25ae36d17d46616139db5` (`bind inner sessions to node
identity`). Session hellos bind the node UUID and ephemeral X25519 public key
to the enrolled Ed25519 identity signature and negotiated transcript. Receivers
reject a different identity or transcript before deriving the encrypted session.

Production relay deployment, physical direct-to-relay failover, package build,
and full cross-platform security verification remain out of scope.

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
| Full suite with `--cov=barn_compute --cov-report=term-missing` | PASS — 63 passed in 4.26s; 80% coverage |

The full suite emitted one known Starlette `TestClient` deprecation warning
concerning `httpx`. It did not affect assertions or the test outcome.

## Command

```sh
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  ./.venv-heartbeat-test/bin/python -m pytest -p pytest_cov -q \
  --cov=barn_compute --cov-report=term-missing
```

## Remaining checks

Production relay deployment, physical direct-to-relay failover, package build,
`twine check`, archive screening, clean-wheel installation, and physical
two-node networking remain not run for this checkpoint.
