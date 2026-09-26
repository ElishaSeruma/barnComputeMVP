# Windows integrated M1 runtime verification - 2026-09-26

## Scope and environment

Integrated runtime following the Mac identity-handshake evidence pulled at
`c61f0ed`. This verifies local logical nodes and real sockets on Windows;
physical Windows/macOS and public relay acceptance remain separate gates.

- Windows 11, build 10.0.26200, AMD64.
- Python 3.12.10.
- Editable development environment `.venv-heartbeat`.
- Independent clean-wheel environment `.venv-m1-wheel`; the imported package
  resolves under its `Lib/site-packages/barn_compute`, without editable install.
- Clean dependencies include cryptography 45.0.7, FastAPI 0.141.1, HTTPX
  0.28.1, Pydantic 2.13.5, Uvicorn 0.54.0, websockets 15.0.1 and pytest 8.4.2.

## Verification

| Check | Evidence |
| --- | --- |
| Ruff | PASS |
| Initial expanded source suite | 79 PASS, 1 skipped, 81% coverage, 325.98 seconds |
| Initial clean-wheel complete suite | 81 PASS, 1 skipped, 282.83 seconds |
| Listener shutdown regression | 2 PASS |
| Final administrative/audit unit suite | 64 PASS, 1 skipped, 38.29 seconds |
| Loopback admin refusal and redaction | Focused client/CLI tests PASS |
| Windows junction path protection | PASS without symlink privileges |
| Final source suite | 82 PASS, no skips, 343.01 seconds; 82% source coverage |
| Final wheel suite with coverage | 81 PASS, 1 skipped, 348.11 seconds; 82% coverage |
| Final invalid-config secret redaction | 2 focused tests PASS after the full runs |
| Wheel/sdist build | PASS |
| Twine wheel/sdist validation | PASS |
| Archive screening | PASS after excluding local tool caches |
| Clean wheel CLI/version/import origin | PASS |

The initial symlink skip was replaced with a Windows directory-junction
fallback and rerun successfully. The final source suite includes that case.
The installed-wheel run collected the earlier test before the junction fallback
was added, accounting for its single skip. The two full suites ran concurrently;
source coverage was filtered separately: 2,212 of 2,700 statements (81.93%).
Use distinct `COVERAGE_FILE` paths when running coverage suites concurrently.
The known Starlette TestClient/httpx deprecation warning is unrelated to
assertions. Earlier build diagnostics found `.uv-cache` inside the sdist; the
sdist now has an explicit source allowlist and CI screens both archives.

The direct TLS source-UUID check initially failed because HTTPX's internal
SSL object required positional `getpeercert(True)`. That was corrected and
all direct boundary tests reran successfully before the complete reruns.

## Real network coverage

Disposable coordinator, peer and relay services bind real TLS/WSS loopback
sockets on ephemeral ports. The tests cover:

- Source-owned signed remote share creation and recipient inbox/grants.
- Direct HTTPS boundary files and deterministic 100 MiB files in both directions.
- WSS relay 100 MiB files in both directions, with matching SHA-256.
- Renewed grants preserving transfer UUIDs and preverified chunk reuse.
- Automatic direct-port failure falling back to the configured secure relay.
- Signed recipient proof, durable nonce rejection and live share/node revocation.
- Unknown CA rejection and source certificate UUID verification.
- Signed relay admission, duplicate connections and out-of-scope routing refusal.
- Inner-session identity signatures, distinct direction keys and counter replay rejection.
- Missing/corrupt chunk repair, cancellation/resume and retained managed copies.
- Concurrent no-clobber exports, request bounds, manifest layout and unsafe paths.
- Paired listeners shutting down on either normal stop or failure.

A sampled Windows test-worker peak working set was 114,245,632 bytes
(approximately 109 MiB) during the source suite with coverage. All logical
services shared that process. This is a local observation, not a physical
per-node performance measurement or a promised upper bound.

## Reproduction

```powershell
uv pip install --python .venv-heartbeat\Scripts\python.exe -e '.[dev]'
.venv-heartbeat\Scripts\ruff.exe check .
$env:COVERAGE_FILE = '.coverage-windows-source'
.venv-heartbeat\Scripts\python.exe -m pytest -q --cov=barn_compute --cov-report=term-missing
.venv-heartbeat\Scripts\python.exe -m build
.venv-heartbeat\Scripts\python.exe -m twine check dist/barncompute-0.1.0a1-py3-none-any.whl dist/barncompute-0.1.0a1.tar.gz
.venv-heartbeat\Scripts\python.exe scripts/check_artifacts.py
```

Final local XML evidence is saved under the ignored `local-state` directory.
Mac instructions are in `M1_ACCEPTANCE_RUNBOOK.md` and
`mac_instructions/2026-09-26-integrated-m1.md`.

## Remaining acceptance gates

Mac rerun of this integrated commit, public relay deployment, actual two-host
transfers/failover, resource measurements on each host, and TestPyPI installation
provenance remain NOT RUN. Owner-supplied relay hosting/domain/TLS and release
credentials are required. M1 must not be marked accepted from local tests alone.
