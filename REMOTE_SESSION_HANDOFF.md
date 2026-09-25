# barnCompute remote-session handoff

Prepared: 2026-09-25  
Repository: `barnComputeMVP`  
Branch: `main`  
Current commit at preparation: `7ef770c` (`run`)

## Purpose of the new session

Continue implementing and verifying the `barnCompute` M1 release while working
with the Mac directly. The immediate purpose of the remote session is to inspect
the Mac checkout and environment, rerun the expanded test suite there, diagnose
any platform-specific problem from real output, and then continue the node
identity and enrolment implementation.

Do not restart the project or replace the existing architecture. Read this file,
`README.md`, `docs/architecture.md`, `docs/protocol-v1.md`,
`docs/next-steps.md`, and `docs/test-report.md` before changing code.

The original requirements were supplied in these documents on the Windows
machine:

- `CODEX_M1_IMPLEMENTATION_SPEC.md`
- `TESTPYPI_AND_CROSS_PLATFORM_TEST_PLAN.md`
- `PUBLIC_WIFI_FALLBACK_ADDENDUM.md`
- `START_HERE_FOR_CODEX.md`

Treat them as specifications and reference material, not as evidence that work
or testing has already occurred. The public-Wi-Fi addendum overrides the
original direct-only transport exclusion: M1 now requires an optional secure
outbound WSS relay fallback while retaining inner endpoint authentication and
encryption.

## Product goal

M1 creates a private group of authenticated devices called a Barn. A macOS host
can run the coordinator and a normal node agent; a Windows host runs another
node agent. The completed release must support:

- Explicit, verified node enrolment and coordinator approval.
- Durable device identities and Barn trust state.
- Authenticated heartbeats and useful reachability diagnostics.
- Explicit import of files into immutable managed storage.
- Recipient-specific, expiring read shares.
- Direct authenticated peer HTTPS transfers when reachable.
- Optional outbound-only relay fallback for client-isolated public Wi-Fi.
- End-to-end authentication and encryption inside the relay tunnel.
- Fixed 1 MiB chunks, durable resume journals, per-chunk hashes, and final
  SHA-256 verification.
- Installation of the exact same TestPyPI release on Python 3.11 or 3.12 on
  physical macOS and Windows computers.

Distribution name: `barnCompute`  
Import name: `barn_compute`  
CLI: `barn`  
Current prerelease version: `0.1.0a1`  
Production PyPI publication is out of scope.

## Security boundaries

- Never disable TLS verification or add an insecure HTTP fallback.
- Never print, log, commit, or package private keys, bearer tokens, invite
  codes, credentials, file contents, or absolute private source paths.
- A relay ticket is transport admission only. It is not node approval or a file
  grant.
- The relay must not decrypt managed file content or act as the coordinator.
- Node signatures authenticate identity but do not authorize file access.
  Coordinator-signed, recipient-specific grants are also required.
- Local administration must bind to loopback only.
- Never disable the operating-system firewall or create router port forwards.
- TestPyPI upload requires separate explicit owner authorization and securely
  configured TestPyPI credentials. Do not publish merely because artifacts
  build successfully.
- Tests requiring two physical machines, a deployed relay, or TestPyPI must be
  recorded as `NOT RUN` until they actually happen.

## Completed implementation

The following is implemented and committed:

- PEP 621 `pyproject.toml`, `src/` package layout, Apache 2.0 packaging, and
  `barn` console entry point.
- Python 3.11 and 3.12 constraints.
- Strict configuration, protocol models, and typed error codes.
- Ed25519 signed-request canonicalisation and verification.
- Timestamp checks and durable SQLite nonce replay prevention.
- Private Ed25519 identity serialization and platform-specific state paths.
- CLI command hierarchy, config commands, initial `doctor`, and explicit
  `NOT_IMPLEMENTED` behavior for unfinished commands.
- Atomic coordinator initialization in a private staging directory.
- Random Barn ID, Ed25519 Barn CA, public CA certificate, SAN-bound coordinator
  TLS certificate, separate grant-signing key, and random admin bearer token.
- Coordinator SQLite schema and initial migration.
- Public CA export with SHA-256 fingerprint.
- Expiring one-use invitation creation using 192 random bits; only the SHA-256
  digest is persisted.
- Unit tests and Windows/macOS GitHub Actions definition.
- Documentation of architecture, protocol foundation, status, and acceptance
  evidence.
- Cross-platform `.gitignore` entries for virtual environments, Apple metadata,
  caches, coverage, build output, databases, certificates, tokens, logs, and
  local state.

## Verified evidence

### Windows

- Python 3.12.10.
- Ruff passed.
- Expanded coordinator-foundation suite: 18 tests passed.
- Coverage at that checkpoint: 84%.
- Wheel and source distribution built successfully.
- `twine check dist/*` passed for both artifacts.
- Disposable CLI test passed for coordinator initialization, CA export, matching
  CA fingerprints, and invitation creation.

### macOS foundation checkpoint

- Apple Silicon Mac.
- Python 3.12.14.
- Ruff passed.
- Earlier foundation suite: 12 tests passed with 84% coverage.
- Wheel and source distribution built successfully.
- Twine passed for both artifacts.
- Mac-built wheel SHA-256:
  `69d8d2c6ffb8e3ef779bdd358b2f5dda47b048f271b3e6a600e2a34c081717e3`
- Mac-built source distribution SHA-256:
  `d959e6b40969882ed0fb5eb532a8b11810a3799409b090e137effe317afcb351`

These hashes describe the earlier foundation build. They are not the current
coordinator-enhanced artifact and are not TestPyPI acceptance artifacts.

The Mac initially produced `ModuleNotFoundError: No module named
'barn_compute'` from an editable-install launcher after a build. The user later
reported that the clean wheel workflow worked. Do not assume the editable issue
still exists; verify the current checkout directly.

## Current repository components

```text
src/barn_compute/
  __init__.py
  auth.py
  cli.py
  config.py
  crypto.py
  errors.py
  models.py
  coordinator/
    __init__.py
    repository.py
    service.py

tests/unit/
  test_auth.py
  test_cli.py
  test_config.py
  test_coordinator_service.py
  test_crypto.py
  test_models.py
```

Local build output, virtual environments, certificates, databases, and secrets
are intentionally ignored and must not be committed.

## First actions in the Mac remote session

From the Mac repository root:

```bash
git status --short
git branch --show-current
git log -5 --oneline
git pull --ff-only

python3.12 -m venv .venv-test
PY="./.venv-test/bin/python"
"$PY" -m pip install --upgrade pip
"$PY" -m pip install --verbose --editable '.[dev]'

"$PY" -m ruff check .
"$PY" -m pytest -q --cov=barn_compute
"$PY" -m build
"$PY" -m twine check dist/*
"$PY" -m pip check
./.venv-test/bin/barn --version
./.venv-test/bin/barn --help
```

Expected expanded result: 18 tests pass. If a command fails, preserve the exact
output and diagnose it before changing dependencies or deleting state.

Exercise the coordinator only with disposable state:

```bash
TEST_ROOT="$(mktemp -d)"

./.venv-test/bin/barn coordinator init \
  --name LabBarn \
  --advertise 127.0.0.1 \
  --state-dir "$TEST_ROOT/coordinator"

./.venv-test/bin/barn coordinator ca export \
  --output "$TEST_ROOT/barn-ca.pem" \
  --state-dir "$TEST_ROOT/coordinator"

./.venv-test/bin/barn coordinator invite \
  --ttl 10m \
  --state-dir "$TEST_ROOT/coordinator"
```

The fingerprints from `init` and `ca export` must match. The displayed invite is
disposable but should still be treated as a secret. Do not paste real future
invite codes into chat or logs.

Record the exact macOS version, architecture, Python version, pip version, test
count, coverage, Twine result, and newly built artifact hashes in
`docs/test-report.md`. Do not overwrite the earlier hashes; label the new hashes
with their implementation checkpoint.

## Immediate implementation target

Continue the coordinator trust and enrolment slice:

1. Implement durable node initialization with a distinct Node ID and Ed25519
   identity retained across restarts.
2. Generate a TLS CSR whose SAN matches the node's explicit advertised IP or
   hostname.
3. Implement enrolment challenge and identity proof of possession.
4. Verify one-use invitation digest and expiry without logging the code.
5. Store a pending enrolment request; a valid invite must not auto-approve it.
6. Add coordinator listing, explicit approval/rejection, idempotent certificate
   issuance, receipt-bound result polling, and invitation consumption.
7. Bind the coordinator grant public key to the trusted Barn response.
8. Reject duplicate Node IDs with conflicting keys, expired or reused invites,
   malformed CSRs, wrong SANs, invalid proofs, and unsupported protocol majors.
9. Add persistence and negative tests before introducing network services.

The next slice after this is public HTTPS plus loopback admin APIs, followed by
signed heartbeats and liveness.

## Work that remains unimplemented

- Node initialization and enrolment approval.
- Coordinator and node HTTP services.
- Heartbeats, registry refresh, state transitions, and reconnect logic.
- Complete `barn doctor` checks.
- Immutable managed-file import and quota enforcement.
- Shares, signed transfer grants, peer serving, download journals, resume,
  cancellation, assembly, and export.
- Relay service, admission tickets, multiplexing, flow control, inner protected
  sessions, and transport failover.
- Full integration, security, packaging, and physical acceptance matrices.
- Runtime dependency locks for controlled TestPyPI installation.
- TestPyPI publication and installation provenance.

## Definition of M1 completion

M1 is complete only after the same authorized TestPyPI artifact is installed in
clean environments on the physical Mac and Windows machines and demonstrates:

- Explicit enrolment and approval with persistent identities.
- Correct liveness and revocation behavior.
- A verified 100 MiB transfer in both directions.
- Interrupted-transfer resume without re-downloading verified chunks.
- Rejection of unauthorized, expired, revoked, forged, and replayed access.
- Matching final SHA-256 values.
- Direct-LAN operation.
- Client-isolation operation through a real deployed secure relay, including
  relay outage and direct-to-relay failover.

Until then, the release verdict remains `NOT YET RUN` or `BLOCKED`, never `PASS`.

