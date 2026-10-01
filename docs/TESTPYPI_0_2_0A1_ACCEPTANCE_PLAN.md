# barnCompute 0.2.0a1 — TestPyPI Release and Cross-Platform Acceptance Plan

## 1. Release purpose

`barnCompute==0.2.0a1` is the first M2 TestPyPI prerelease.

It must prove that the M1 secure device/transport substrate can support the first distributed Barn Storage Fabric:

- BRG v0;
- NBO decision framework;
- Bays;
- encrypted storage fragments;
- two-copy desired placement;
- distribution matrix;
- Placement NBO v0;
- DT-NBO v0;
- location-independent retrieval;
- Resilience NBO v0.

This release is experimental and TestPyPI-only.

## 2. Preconditions

Before upload:

- M1 closure report is current.
- Public-Wi-Fi control/data fallback used by M2 has passed the required M1 closure tests.
- `main` or the release branch is clean.
- package version is `0.2.0a1`;
- Python requirement remains explicitly documented;
- Apache-2.0 license remains intentional;
- changelog describes M2 additions and compatibility;
- old `0.1.0a1` state-migration tests pass;
- CI passes on macOS and Windows;
- wheel/sdist screening passes;
- owner explicitly authorizes TestPyPI upload.

Do not upload to production PyPI.

## 3. Build gate

From a clean development environment:

```bash
python -m pip install -e '.[dev]'
python -m ruff check .
python -m pytest -q --cov=barn_compute --cov-report=term-missing
python -m build
python -m twine check dist/*
python scripts/check_artifacts.py
```

Record:

- Git SHA;
- Python version;
- test count;
- coverage;
- wheel filename/SHA-256;
- sdist filename/SHA-256.

Verify the archives contain no:

- private keys;
- coordinator/node state;
- SQLite runtime DBs;
- relay TLS private key;
- invite codes;
- bearer tokens;
- TestPyPI credentials;
- user files;
- local absolute paths;
- test journals/fragment stores.

## 4. TestPyPI upload

Use only the TestPyPI repository and securely configured credentials:

```bash
python -m twine upload --repository testpypi dist/*
```

Do not pass a token on the command line.

Verify the published `0.2.0a1` release exists and record the exact published wheel SHA-256.

If any uploaded artifact is wrong, increment the prerelease (`0.2.0a2`, etc.). Never attempt to replace an accepted TestPyPI artifact under the same version.

## 5. Clean installation rule

On macOS and Windows, create fresh environments.

Install dependencies separately from production PyPI. Then install `barnCompute` only from TestPyPI with `--no-deps`.

Conceptual command:

```bash
python -m pip install --index-url https://test.pypi.org/simple/ --no-deps 'barnCompute==0.2.0a1'
```

Preserve a redacted verbose install log proving the artifact came from TestPyPI.

Record:

- OS/build;
- architecture;
- Python;
- pip;
- package version;
- download URL/source;
- downloaded wheel SHA-256;
- `pip check`;
- `barn --version`.

## 6. Upgrade/migration acceptance

Use a **copy** of known-good `0.1.0a1` state.

Never make the first migration test against the only copy of real user state.

Test:

1. install/run `0.1.0a1`;
2. create/verify M1 Barn/node state and at least one managed file/share;
3. back up state;
4. install `0.2.0a1`;
5. start coordinator/node;
6. allow documented migrations;
7. verify:
   - same Barn ID;
   - same Node ID;
   - same trust root;
   - existing M1 managed file exists;
   - existing M1 file sharing still works;
   - migration is not repeated destructively on restart;
   - BRG/M2 tables are initialized cleanly.

Rollback behavior must be documented. Do not promise automatic downgrade if schema changes make it unsafe.

## 7. M1 regression matrix on 0.2.0a1

At minimum rerun:

- node enrolment/approval;
- heartbeat/registry;
- direct Mac→Windows 100 MiB M1 share;
- direct Windows→Mac 100 MiB M1 share;
- matching SHA-256;
- interruption/resume;
- revoked/expired/wrong-recipient denial;
- public relay forced transfer;
- blocked-direct `auto` fallback;
- coordinator control fallback required for client-isolated Wi-Fi;
- relay outage fails closed.

M2 cannot be accepted if it breaks M1.

## 8. M2 functional acceptance matrix

Use PASS / FAIL / NOT RUN with commands, UTC timestamps and evidence.

| ID | Test | Expected result |
|---|---|---|
| M201 | BRG node snapshots | Mac and Windows create distinct durable snapshots with storage/capability data. |
| M202 | Directional links | Mac→Windows and Windows→Mac are separate; direct and relay observations are separate. |
| M203 | BRG restart persistence | Restart coordinator; historical observations and aggregates remain. |
| M204 | NBO deterministic decision | Same fixture/snapshot/policy yields same Placement decision. |
| M205 | NBO hard filters | Revoked/incompatible/insufficient-space node cannot win a soft score. |
| M206 | Decision outcome ledger | Success/failure is linked to immutable decision without rewriting it. |
| M207 | Bay create/persist | Bay survives restart with policy intact. |
| M208 | Add boundary files | 0 B, 1 B, 8 MiB−1, 8 MiB, 8 MiB+1 produce valid storage manifests. |
| M209 | Fragment encryption | Stored fragment bytes are ciphertext; plaintext is not present as fragment payload. |
| M210 | AEAD tamper | Modified ciphertext or AAD is rejected. |
| M211 | STANDARD_2X placement | Each fragment reaches two distinct Node IDs when two eligible nodes exist. |
| M212 | Matrix desired/observed | Planned replica is not marked healthy before verified durable receipt. |
| M213 | Placement ledger | Candidate scores/rejections and selected nodes are inspectable. |
| M214 | DT-NBO source selection | With multiple healthy sources, selected source follows deterministic BRG rule. |
| M215 | DT-NBO route | Direct/relay selection uses security policy plus BRG evidence; no insecure downgrade. |
| M216 | Location-independent get | Retrieval command requires Bay/file identity, not original source host. |
| M217 | Original importer offline | After successful 2x placement, origin goes offline and another node reconstructs matching file. |
| M218 | Replica fallback | One replica is unavailable/corrupt; retrieval uses another healthy replica. |
| M219 | Multi-source retrieval | One file is reconstructed from fragments fetched from more than one source in integration fixture. |
| M220 | Full-file integrity | Reconstructed output size and SHA-256 equal original. |
| M221 | Coordinator restart | Bay/matrix/BRG/NBO state survives restart. |
| M222 | Node restart | Encrypted fragments and receipts survive restart. |
| M223 | Resilience grace | Temporary outage marks degradation but does not immediately duplicate data before grace. |
| M224 | Three-node repair integration | After grace, healthy source→new destination repair returns desired replica count. |
| M225 | Insufficient nodes | Two-node Barn with one offline remains DEGRADED with clear `no eligible repair target`, not fake-healthy. |
| M226 | Revoked storage node | Revoked node is excluded from reads/new placement/repair authority. |
| M227 | Storage grant scope | M1 share grant cannot be reused as arbitrary fragment write/read grant. |
| M228 | No-clobber export | Existing output is preserved. |
| M229 | Concurrent retrieval/placement | Bounded concurrent operations complete without corrupting matrix or journal. |
| M230 | M1 state compatibility | Existing M1 file/share remains usable after M2 migration. |

## 9. Physical two-host scenario

The owner currently has macOS and Windows as the primary physical test pair.

With `STANDARD_2X` and only two eligible Node IDs, every fragment can be stored on both nodes.

Required physical demonstration:

```text
Mac + Windows join Barn
    ↓
create Bay
    ↓
add deterministic file (recommend 500 MiB for M2 physical test)
    ↓
Barn fragments + encrypts
    ↓
Placement NBO places two verified replicas per fragment
    ↓
distribution matrix HEALTHY
    ↓
record BRG/NBO decisions
    ↓
stop original importing node
    ↓
remaining node performs location-independent retrieval
    ↓
output SHA-256 matches original
    ↓
Bay reports DEGRADED while peer is offline
    ↓
Barn does not claim repair when no third eligible node exists
```

This proves source independence and correct degraded behavior.

## 10. Three-node repair scenario

Automated three-node integration is mandatory.

A three-physical-device repair test is strongly recommended but not mandatory for the first `0.2.0a1` Mac/Windows package gate if a third physical host is unavailable.

When available:

```text
Nodes A, B, C
replication factor = 2

fragment replicas = A + B
    ↓
A becomes unavailable past grace
    ↓
Resilience NBO
    ↓
Placement NBO chooses C
    ↓
DT-NBO selects B → C
    ↓
encrypted fragment copied + verified
    ↓
matrix returns HEALTHY (B + C)
```

Record decision IDs and evidence that the NBO interfaces—not ad hoc repair code—made destination/path choices.

## 11. Public-Wi-Fi M2 scenario

Because M2 depends on M1's network substrate, test on client-isolated conditions:

- no direct peer LAN path;
- no direct node→Mac-coordinator LAN path;
- outbound TCP 443 allowed;
- coordinator and nodes use the accepted outbound fallback control path;
- file fragment movement uses secure relay;
- Bay operations, BRG updates and NBO authorization still work;
- location-independent retrieval succeeds;
- revocation still fails closed.

This is critical: M2 must not be "distributed" only on friendly LANs.

## 12. Resource observations

For at least one 500 MiB Bay placement/retrieval run, capture:

- coordinator RSS/working set;
- each node agent RSS/working set;
- disk before/after;
- fragment-store growth;
- BRG DB growth;
- NBO ledger growth;
- peak concurrent transfer count;
- elapsed placement time;
- elapsed retrieval time;
- bytes sent direct vs relay;
- retry count.

These are measurements, not performance promises.

## 13. Release report

Create:

`docs/M2_0_2_0a1_TESTPYPI_ACCEPTANCE.md`

Minimum fields:

```text
Release: barnCompute==0.2.0a1
Git SHA:
TestPyPI release:
Wheel SHA-256:
sdist SHA-256:

M1 closure status:
M1 regression status:

Mac:
  OS/arch/Python/pip:
  install provenance:
  test result:

Windows:
  OS/arch/Python/pip:
  install provenance:
  test result:

Migration 0.1.0a1 → 0.2.0a1:
BRG tests:
NBO tests:
Bay/fragment tests:
Encryption tests:
Placement tests:
DT-NBO tests:
Location-independent retrieval:
Resilience tests:
Public relay/control fallback:
Resource measurements:

Known issues:
Blocking defects:
Verdict: PASS / BLOCKED / NOT YET RUN
Human reviewer:
UTC date:
```

## 14. `0.2.0a1` acceptance definition

The release candidate passes only if:

- same TestPyPI artifact provenance is established on both physical hosts;
- all automated Windows/macOS suites pass;
- M1 regression passes;
- M1 public-Wi-Fi substrate used by M2 is accepted;
- migrations preserve old identities/state;
- Bay storage produces encrypted distributed replicas;
- BRG records real operational observations;
- Placement/DT/Resilience decisions are persisted and explainable;
- source-independent physical retrieval succeeds;
- three-node automated repair succeeds;
- security/tamper/authorization tests fail closed;
- no blocking defect remains.

Production PyPI remains a separate future owner decision.
