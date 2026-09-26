# Integrated M1 runtime verification

Follow `../M1_ACCEPTANCE_RUNBOOK.md` for the complete current instructions.
The earlier 63-test checkpoint is superseded by the integrated runtime suite.
All hosts and the relay must use this updated code together: ticket signatures
now include identity keys and admission requires a fresh signed challenge.

## Required Mac actions

1. Pull `main` in `/Users/elisha/Developer/barnComputeMVP`.
2. Create `.venv-m1` with Python 3.11/3.12 or refresh an existing local environment
   using `python -m pip install -e '.[dev]'`. The websockets dependency is new.
3. Run Ruff and the full suite with coverage. Expect 82 collected tests. Windows
   uses a directory junction when symlink creation is unavailable; Mac uses a
   symlink. Both paths exercise refusal to follow managed-store links. Report
   any skip explicitly.
4. Run build, Twine and `python scripts/check_artifacts.py`.
5. Install the built wheel in a separate clean environment, confirm its import
   resolves under that environment's site-packages, and smoke-test `barn`.
6. Record commit, environment, test counts, coverage, duration, warnings,
   hashes and all failures under `docs/mac_test_results`.

Automated tests deploy their own disposable local HTTPS/WSS listeners and need
no public relay or credentials. They include 100 MiB direct and relay transfers
in both directions, real fallback and security/recovery cases. Allow several
minutes and approximately 2 GiB free temporary disk space.

The final milestone additionally requires the physical/public relay and
released TestPyPI installation sections of the central runbook. Those gates
remain NOT RUN until the owner supplies the server/domain/certificate and
release credentials and records real results.
