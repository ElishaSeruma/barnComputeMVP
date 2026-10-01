# barnCompute M2.1–M2.9 Implementation Specification

## 1. Milestone

Target TestPyPI prerelease:

`barnCompute==0.2.0a1`

M2 turns M1's secure file-exchange substrate into the first Barn Storage Fabric.

M1 answers:

> Can two authenticated nodes safely exchange a managed file?

M2 answers:

> Can a Barn place, preserve and retrieve encrypted file data across its nodes without depending on the original source node?

## 2. Strict scope

`0.2.0a1` includes:

- M2.1 BRG v0;
- M2.2 NBO framework and decision ledger;
- M2.3 Bays;
- M2.4 M2 storage fragments and encrypted replicas;
- M2.5 distribution matrix;
- M2.6 Placement NBO v0;
- M2.7 DT-NBO v0;
- M2.8 location-independent retrieval;
- M2.9 Resilience NBO v0 and repair.

It must preserve M1 direct/relay sharing behavior.

It does not include:

- erasure coding;
- Capacity NBO;
- Integrity/Scrub NBO;
- distributed compute;
- AI inference;
- BALL/EDHE;
- multi-Barn federation;
- public anonymous links;
- marketplace/economics;
- mobile agents;
- production PyPI.

## 3. Package/module additions

Recommended structure:

```text
src/barn_compute/
  brg/
    __init__.py
    models.py
    repository.py
    collector.py
    aggregates.py
    queries.py

  nbo/
    __init__.py
    base.py
    decisions.py
    placement.py
    transport.py
    resilience.py

  storage/
    __init__.py
    bay.py
    fragments.py
    crypto.py
    distribution.py
    planner.py
    recovery.py
    repository.py
```

Refactor if the repository has a cleaner compatible seam, but preserve these responsibilities.

Existing M1 modules remain the low-level network/identity/transfer substrate.

## 4. Protocol compatibility

Do not automatically bump the wire major version solely because the package becomes `0.2.0a1`.

Prefer compatible additions:

```text
protocol_version: existing major
features:
  - brg_v0
  - bays_v1
  - fragment_storage_v1
  - placement_nbo_v0
  - dt_nbo_v0
  - resilience_nbo_v0
```

A node that lacks required M2 storage features may remain an approved M1 peer but must be ineligible for M2 placement.

Never confuse software package version with wire protocol version.

## 5. State migration

### Coordinator

Add transactional migrations for:

- BRG tables;
- NBO decision/outcome tables;
- Bays;
- logical files/file versions;
- distribution matrix;
- fragment desired/observed state;
- wrapped encryption keys/metadata;
- repair plans.

### Node

Add migrations for:

- stored M2 fragment metadata;
- encrypted fragment store;
- fragment receipts;
- fragment operation journal;
- M2 storage quota/limits.

Requirements:

- preserve Barn ID;
- preserve node IDs;
- preserve CA/trust material;
- preserve M1 managed files;
- preserve M1 shares/transfers/journals;
- never silently delete old state;
- migration must be transactional/idempotent where practical;
- backup instructions must be documented before the first physical upgrade.

Existing M1 files are **not automatically converted** into Bays. Provide an explicit operator action to add/import an existing managed file into a Bay.

## 6. M2.1 — BRG v0

Implement `BRG_AND_NBO_V0_SPEC.md`.

Required outcomes:

- coordinator can persist node snapshots;
- coordinator can persist directional direct/relay link observations;
- existing M1 transfers can feed BRG observations without changing their authorization semantics;
- BRG aggregates update deterministically;
- storage/free-space snapshots are collected safely;
- history is bounded/configurable;
- BRG queries are available to NBO services;
- `barn brg nodes`, `barn brg links`, `barn brg node <NODE_ID>` and `--json` equivalents expose non-secret diagnostics.

Acceptance:

- two nodes generate distinct node snapshots;
- Mac→Windows and Windows→Mac are separate edges;
- direct and relay are separate edge modes;
- failed transfer increments failure evidence without overwriting previous success history;
- restart preserves BRG history.

## 7. M2.2 — NBO framework and decision/outcome ledger

Implement:

```text
NBO.evaluate(context) -> Decision
```

with no storage side effects.

Required:

- versioned optimizer identity;
- immutable decision ID;
- candidate set;
- hard-filter rejections;
- component scores;
- selected action;
- reason codes;
- BRG snapshot/version reference;
- executor outcome linked to decision;
- deterministic tie-break rules;
- audit-safe CLI inspection.

Acceptance:

- a decision can be replayed from the same fixture and returns the same result;
- a failed executor operation records a failed outcome without rewriting the original decision;
- no secret material appears in decision JSON/logs.

## 8. M2.3 — Bay model

A Bay is the user-visible logical distributed storage container.

Minimum entities:

```text
Bay
  bay_id
  name
  owner
  created_at
  policy_id
  replication_factor
  encryption_policy
  status

LogicalFile
  logical_file_id
  bay_id
  display_name

FileVersion
  version_id
  logical_file_id
  original_size
  full_plaintext_sha256
  fragment_size
  fragment_count
  created_at
  state
```

Initial policy:

```text
STANDARD_2X
replication_factor = 2
```

CLI:

```text
barn bay create <NAME>
barn bay list
barn bay show <BAY_ID>
barn bay add <BAY_ID> <LOCAL_FILE>
barn bay files <BAY_ID>
barn bay get <BAY_ID> <LOGICAL_FILE_OR_VERSION> --output <PATH>
barn bay health <BAY_ID>
```

Destructive Bay/file deletion can be deferred unless implemented with explicit retention/replica cleanup semantics.

Acceptance:

- Bay survives coordinator restart;
- file version is immutable;
- two files with same display name can be versioned/disambiguated safely;
- no user path becomes a remote storage identifier.

## 9. M2.4 — Storage fragments and encrypted replicas

### 9.1 Distinguish transport chunks from storage fragments

M1:

```text
1 MiB transport chunks
```

M2:

```text
storage fragments (default proposed: 8 MiB, configurable)
```

A storage fragment may itself be transferred using multiple M1 transport chunks.

Never reuse M1 chunk index as the M2 placement identity.

### 9.2 Fragment entity

```text
fragment_id
version_id
index
plaintext_offset
plaintext_length
plaintext_sha256
ciphertext_length
ciphertext_sha256
encryption_algorithm
nonce
aad_version
```

### 9.3 Encryption v0

M2 requires authenticated encryption at rest.

Use an established AEAD from `cryptography`; do not invent cryptography.

Recommended model for this early release:

- random 256-bit per-file Data Encryption Key (DEK);
- each fragment encrypted independently;
- unique nonce per encrypted fragment under that DEK;
- authenticated associated data binds:
  - Barn ID
  - Bay ID
  - file-version ID
  - fragment ID
  - index
  - plaintext length
  - crypto format version;
- coordinator remains the trusted key authority for M2 v0;
- DEKs are persisted only wrapped/encrypted by a coordinator-local Key Encryption Key held in private coordinator state;
- storage nodes persist ciphertext, not plaintext fragments;
- retrieving an authorized file obtains required decryption material only through the trusted coordinator path.

This preserves M1's existing trust boundary: M2 v0 does not promise confidentiality from a compromised coordinator.

Future user-controlled/decentralized key custody is out of scope.

### 9.4 Safe fragment commit

Receiver flow:

```text
receive encrypted bytes
    ↓
validate expected length/hash
    ↓
fsync private temporary file
    ↓
atomic rename to fragment store
    ↓
persist verified receipt
    ↓
report observed replica
```

Never mark a replica healthy before durable bytes exist.

Acceptance:

- fragment on-disk bytes differ from plaintext;
- modified ciphertext fails verification/decryption;
- metadata substitution/AAD mismatch fails;
- zero-length logical files remain valid;
- fragment operations are bounded in memory.

## 10. M2.5 — Distribution matrix

The matrix stores desired state separately from observed state.

Minimum model:

```text
fragment_id
desired_replica_count

ReplicaAssignment
  replica_id
  fragment_id
  node_id
  role
  desired_state
  observed_state
  assigned_at
  verified_at
  last_seen_at
  ciphertext_sha256
```

Observed replica states:

```text
PLANNED
TRANSFERRING
HEALTHY
UNAVAILABLE
CORRUPT
REMOVING
REMOVED
FAILED
```

Derived fragment health:

```text
HEALTHY
DEGRADED
REPAIR_PENDING
REPAIRING
UNAVAILABLE
LOST
```

Rules:

- matrix updates are transactional;
- desired placement never implies actual durable storage;
- only verified receipts create `HEALTHY`;
- deleting/moving a replica uses copy→verify→commit→remove;
- offline nodes do not automatically become LOST.

CLI:

```text
barn storage matrix <FILE_VERSION_ID>
barn storage replicas <FRAGMENT_ID>
barn bay health <BAY_ID>
```

## 11. M2.6 — Placement NBO v0

Implement Placement NBO from the NBO specification.

Initial use cases:

- initial fragment replica placement;
- repair destination selection.

Hard filters:

- active approved node;
- feature compatible;
- sufficient capacity/headroom;
- not revoked;
- not already hosting same replica;
- not explicitly excluded;
- satisfies policy.

Weighted score should include:

- storage headroom;
- historical availability;
- directional transfer quality from current source;
- reliability/integrity evidence available at M2;
- replica diversity.

Do not hard-code weights in protocol models; keep them policy/config versioned.

Acceptance:

- no fragment places both `STANDARD_2X` replicas on the same Node ID;
- ineligible node never wins due to a high soft score;
- candidate/reason ledger is persisted;
- deterministic tie behavior.

## 12. M2.7 — DT-NBO v0

DT-NBO selects:

- healthy source replica;
- destination;
- `direct` or `relay`;
- bounded concurrency/timeout settings;
- fallback path.

Reuse M1 executors.

Do not duplicate:

- signed request logic;
- relay admission;
- transfer journaling;
- integrity verification;
- retry/backoff primitives.

DT-NBO uses BRG directional evidence.

A successful operation writes an outcome back to BRG.

Acceptance:

- source selection changes when one replica is offline;
- direct and relay metrics are not conflated;
- forced security policy cannot be overridden by a score;
- if direct fails under `auto` and secure relay is available, existing verified transport chunks are reused;
- errors distinguish no healthy source, no route, authorization failure and checksum failure.

## 13. M2.8 — Location-independent retrieval

A user requests a Bay logical file/version, not a source node.

Flow:

```text
request version
    ↓
load immutable fragment manifest
    ↓
distribution matrix finds healthy replicas
    ↓
DT-NBO chooses source/path per fragment
    ↓
download encrypted fragments
    ↓
verify ciphertext
    ↓
authorized decryption
    ↓
verify plaintext fragment hash
    ↓
assemble in order
    ↓
verify full-file size + SHA-256
    ↓
safe no-clobber export
```

The original importing node must not be special after successful replicated commit.

Parallelism must be bounded.

M2 should support multiple fragments coming from different nodes during one retrieval.

Acceptance:

- origin node can be offline while another node reconstructs the file from remaining healthy replicas;
- output SHA-256 equals original;
- corrupt/unavailable replica can be skipped when another healthy replica exists;
- no-clobber behavior remains;
- partial retrieval state survives process restart where feasible.

## 14. M2.9 — Resilience NBO v0 and repair

### 14.1 Detection

Trigger evaluation on:

- node liveness change;
- replica verification failure;
- fragment receipt loss/error;
- periodic reconciliation;
- node revocation.

### 14.2 Grace period

Temporary node disappearance must not immediately duplicate large amounts of data.

Policy defines:

```text
repair_grace_seconds
desired_replica_count
```

After grace:

- if healthy replicas < desired and at least one healthy source plus one eligible destination exist, create repair plan;
- otherwise remain degraded with reason.

### 14.3 Repair execution

```text
Resilience NBO identifies deficit
    ↓
Placement NBO selects destination
    ↓
DT-NBO selects source/path
    ↓
encrypted fragment copied
    ↓
destination verifies/commits
    ↓
matrix atomically updated
    ↓
NBO outcome + BRG observation recorded
```

Never delete the last healthy replica as part of repair.

### 14.4 Two-node Barn behavior

With only two eligible physical nodes and replication factor 2, loss of one node may leave the Bay `DEGRADED` but **unrepairable until another eligible node appears**.

That is correct behavior.

Do not fabricate resilience by placing two replicas on one Node ID.

### 14.5 Testing actual repair

Automated integration tests must use at least three isolated Node IDs/state roots.

The mandatory physical release test may use the owner's Mac+Windows pair to prove source-independent retrieval and degraded-state behavior. A true three-physical-device repair test is strongly recommended and should be recorded separately if available.

Acceptance:

- degradation is detected;
- repair waits for grace period;
- replacement destination is selected through Placement NBO;
- source/path is selected through DT-NBO;
- verified replica returns fragment/Bay to healthy state;
- impossible repair reports an actionable degraded reason.

## 15. New coordinator API intent

Exact routes may be adapted to repo conventions, but keep one documented source of truth.

Suggested additions:

```text
GET  /v1/brg/nodes
GET  /v1/brg/nodes/{node_id}
GET  /v1/brg/links
POST /v1/brg/observations

POST /v1/bays
GET  /v1/bays
GET  /v1/bays/{bay_id}

POST /v1/bays/{bay_id}/versions
GET  /v1/versions/{version_id}

GET  /v1/storage/fragments/{fragment_id}/locations
POST /v1/storage/replica-plans
POST /v1/storage/repair-plans

GET  /v1/nbo/decisions/{decision_id}
```

Remote endpoints require existing node request signing/replay protection and scoped authorization.

## 16. Node peer storage API intent

M2 storage operations require a distinct scoped capability/grant from ordinary M1 file-share grants.

Examples:

```text
PUT /v1/storage/fragments/{fragment_id}
GET /v1/storage/fragments/{fragment_id}
HEAD /v1/storage/fragments/{fragment_id}
```

A storage grant should bind:

- Barn ID;
- operation (`write_replica`, `read_replica`, `repair_replica`, optional `remove_replica`);
- fragment ID;
- file-version ID;
- source node;
- destination node;
- ciphertext size/hash;
- expiry;
- decision/plan ID where applicable.

Do not let an M1 share grant authorize arbitrary fragment storage operations.

## 17. CLI additions

Minimum:

```text
barn brg nodes
barn brg node <NODE_ID>
barn brg links

barn nbo decisions
barn nbo decision <DECISION_ID>

barn bay create <NAME>
barn bay list
barn bay show <BAY_ID>
barn bay add <BAY_ID> <FILE>
barn bay files <BAY_ID>
barn bay get <BAY_ID> <FILE_OR_VERSION> --output <PATH>
barn bay health <BAY_ID>

barn storage matrix <VERSION_ID>
barn storage replicas <FRAGMENT_ID>
barn storage reconcile
```

All support useful human output; state/query commands should support `--json`.

## 18. M2 automated test gate

Add unit/integration/security/migration coverage for:

- BRG model validation and retention;
- directional edges;
- NBO deterministic scoring;
- hard-filter precedence;
- decision/outcome persistence;
- Bay persistence/version immutability;
- storage-fragment boundaries;
- AEAD round trips and tamper/AAD rejection;
- distribution desired vs observed state;
- two-copy placement;
- storage grants and authorization;
- direct and relay fragment transport;
- location-independent reconstruction;
- origin node unavailable;
- corrupt/unavailable replica fallback;
- coordinator/node restart;
- resilience grace;
- three-node repair;
- impossible-repair degraded state;
- 0.1→0.2 migrations;
- M1 regression suite;
- wheel/sdist secret screening.

Do not reduce existing M1 security coverage to improve M2 coverage numbers.

## 19. M2 exit condition before TestPyPI

A local release candidate is upload-ready only when:

- Ruff passes;
- complete automated suite passes on Windows and macOS;
- M1 regressions pass;
- migration tests pass;
- build succeeds;
- Twine validates;
- archive screening finds no secrets/local state;
- clean local wheel install passes;
- version is exactly `0.2.0a1`;
- release notes identify experimental M2 semantics;
- M1 closure blockers affecting inherited networking/security are resolved or the upload is explicitly withheld.
