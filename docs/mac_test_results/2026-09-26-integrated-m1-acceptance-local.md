# macOS integrated M1 local acceptance verification — 2026-09-26

## Scope and commit

Local automated and packaging verification of commit
`842bc31a54429010ff5d445eaebbad4ee6833a4b` (`Integrate M1 secure transfers
and relay acceptance workflows`). This record covers only the Mac-local gates
in `M1_ACCEPTANCE_RUNBOOK.md`: fresh environment, lint, the integrated suite,
build, Twine validation, archive screening, and clean-wheel smoke checks.

It does not claim TestPyPI provenance, public-relay deployment, or physical
macOS/Windows acceptance.

## Environment

- macOS 26.6 (build 25G5028f), Apple Silicon (`arm64`).
- Python 3.12.14; pytest 8.4.2; websockets 15.0.1.
- Fresh `.venv-m1` development environment and separate `.venv-m1-wheel`
  clean-wheel environment in a local Developer checkout outside iCloud-managed
  Desktop/Documents storage.
- Test invocation used `PYTHONPATH=src`, `PYTHONDONTWRITEBYTECODE=1`, and
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` with `-p pytest_cov`.

## Results

| Check | Result |
| --- | --- |
| Ruff | PASS — `ruff check .` completed without findings |
| Full local HTTPS/WSS suite | PASS — 82 passed, 1 warning in 61.56s; 82% coverage |
| JUnit report | PASS — generated under ignored local test state |
| Wheel and source distribution build | PASS |
| Twine validation | PASS — wheel and sdist |
| Artifact screening | PASS — wheel SHA-256 `e77f4014ef6f986b3c064e1ec33ecf413beb63f2ae602a328c708c4031699176`; sdist SHA-256 `251b5ef0c8a71e7da0c70af08a252b0492d0b25b47a029d17ba47d594a949399` |
| Clean-wheel install | PASS — dependency check passed; `barn_compute` imported from clean environment `site-packages`; `barn --version` reported `0.1.0a1`; `barn --help` passed |

The suite emitted the known Starlette `TestClient` deprecation warning
concerning `httpx`. It did not affect assertions.

The local integration suite includes disposable loopback HTTPS/WSS listeners,
100 MiB direct and relay transfers in both logical directions, recipient and
relay authentication, revocation, journal reuse, cancellation/resume, automatic
fallback, boundary files, no-clobber export, and unknown-CA rejection. These
are local automated checks, not physical public-relay evidence.

## Commands

```sh
./.venv-m1/bin/python -m ruff check .
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  ./.venv-m1/bin/python -m pytest -p pytest_cov -q \
  --cov=barn_compute --cov-report=term-missing \
  --junitxml=local-state/mac-m1-tests.xml
./.venv-m1/bin/python -m build
./.venv-m1/bin/python -m twine check dist/*
./.venv-m1/bin/python scripts/check_artifacts.py
```

## Remaining acceptance gates

| Gate | Status |
| --- | --- |
| TestPyPI publication and install provenance on both hosts | NOT RUN — requires owner credentials and package publication |
| Physical Mac-to-Windows and Windows-to-Mac LAN transfers | NOT RUN — requires the separate Windows host and real network evidence |
| Deployed public WSS relay, forced relay, outage/recovery, and blocked-direct fallback | NOT RUN — requires owner-provided relay host, DNS, and TLS certificate |
| Physical resource measurements | NOT RUN — requires two live hosts and the deployed relay scenario |

M1 remains **NOT YET RUN / NOT ACCEPTED** until every external gate has real
evidence.
