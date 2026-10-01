# Barn Resource Graph (BRG) and NBO v0 Specification

## 1. Purpose

M2 introduces the first durable resource-intelligence layer in Barn Computing.

The Barn Resource Graph (BRG) is the coordinator's structured view of:

- nodes and their current capabilities;
- node availability history;
- directional node-to-node transport behavior;
- storage capacity and pressure;
- fragment placement and health observations;
- NBO decisions;
- actual outcomes of those decisions.

The first Node Behaviour Optimizers (NBOs) are deterministic/weighted policy engines. They are not machine-learning systems and must not be described as AI.

## 2. Architectural invariant

```text
BRG snapshot
    ↓
NBO.evaluate(context)
    ↓
Decision (no side effect)
    ↓
Planner / executor
    ↓
Measured outcome
    ↓
BRG observation
    ↓
NBO outcome record
```

NBOs must never directly write/delete fragment bytes.

## 3. BRG ownership

For M2:

- the coordinator owns the authoritative BRG and NBO decision ledger;
- nodes measure local state and execution outcomes;
- nodes send signed telemetry/observations;
- the coordinator validates, timestamps and persists observations;
- node IP addresses are locators, never identities;
- BRG records use stable Node IDs.

Federated/distributed BRG ownership is deferred.

## 4. BRG data model

Use SQLite with graph semantics. Do not add a graph-database dependency in M2.

Recommended tables/entities:

```text
brg_nodes
brg_node_snapshots
brg_edges
brg_link_observations
brg_link_aggregates
brg_storage_observations
brg_availability_events
brg_fragment_observations

nbo_decisions
nbo_candidates
nbo_outcomes
```

### 4.1 Node snapshot

Minimum M2 fields:

```text
snapshot_id
node_id
observed_at
software_version
protocol_version
feature_set
node_status
platform
architecture
logical_cpu_count
storage_total_bytes
storage_free_bytes
barn_storage_limit_bytes
barn_storage_used_bytes
managed_fragment_count
boot_epoch
```

Memory/GPU telemetry may be added if available safely, but M2 placement must not depend on optional compute telemetry.

### 4.2 Directional edge

Treat these as different edges:

```text
A → B / direct
B → A / direct
A → B / relay
B → A / relay
```

Minimum link observation:

```text
observation_id
source_node_id
destination_node_id
transport
started_at
completed_at
success
bytes
duration_ms
setup_ms
retry_count
error_code
```

Derived aggregates may include:

```text
sample_count
success_count
failure_count
success_rate
throughput_ewma
setup_latency_ewma
recent_failure_rate
last_success_at
last_failure_at
```

Do not replace historical observations with only one current value.

### 4.3 Storage observation

```text
node_id
observed_at
free_bytes
barn_used_bytes
fragment_count
write_success/failure
read_success/failure
last_storage_error_code
```

### 4.4 Retention

Default recommendation:

- raw high-frequency observations: bounded retention, e.g. 30 days;
- daily/rolling aggregates: retained long-term;
- NBO decision/outcome records: retained long-term unless the owner explicitly purges them;
- never record plaintext filenames/content solely for optimisation.

Make retention configurable and bounded.

## 5. NBO common interface

Suggested conceptual interface:

```python
class NBO:
    name: str
    version: str

    def evaluate(self, context) -> Decision:
        ...
```

Decision object:

```text
decision_id
nbo_name
nbo_version
created_at
trigger
policy_id
input_snapshot_version
action
subject_id
candidate_count
selected_candidates
reason_codes
predicted_cost
predicted_duration_ms
status
```

Candidate rows:

```text
decision_id
candidate_id
eligible
rejection_reason
score
score_components_json
rank
```

Outcome:

```text
decision_id
started_at
completed_at
success
actual_transport
actual_source
actual_destination
actual_bytes
actual_duration_ms
retry_count
integrity_result
error_code
resulting_state
```

Use structured reason codes, not only free-form prose.

## 6. M2 NBOs

### 6.1 Placement NBO v0

Question:

> Which eligible nodes should receive a new storage replica?

Hard filters before scoring:

- approved/active node;
- supports required M2 storage feature;
- not revoked;
- storage endpoint available;
- sufficient free space plus configured headroom;
- Barn allocation limit not exceeded;
- node does not already hold the same replica;
- satisfies Bay policy;
- not an excluded failure-domain candidate where the policy requires separation.

Initial weighted score should be deterministic and configurable.

Recommended starting dimensions:

```text
storage_headroom
availability
transfer_quality_from_source
integrity_reliability
replica_diversity
```

Example default weights may be supplied in configuration, but they are not protocol constants.

Persist:

- all eligible candidates;
- rejected candidates and reason;
- component scores;
- selected node(s);
- policy/version.

Placement NBO does not move bytes. It outputs a placement decision/plan.

### 6.2 DT-NBO v0

Question:

> From which replica, over which transport, and with what bounded transfer settings should Barn move the data now?

M2 DT-NBO extends the existing `direct | relay | auto` mechanism rather than replacing it.

Inputs:

- healthy replica locations;
- recipient node;
- BRG directional link aggregates;
- direct reachability;
- configured relay availability;
- recent failures;
- transfer size;
- per-node load/limits where available.

Outputs:

```text
source_node_id
destination_node_id
preferred_transport
fallback_transport
concurrency
connect_timeout
reason_codes
```

Version 0 rules:

1. eliminate unavailable/untrusted sources;
2. prefer healthy verified replicas;
3. rank sources using recent directional link quality;
4. prefer direct when it is healthy and materially suitable;
5. use relay when direct is unavailable or recent evidence justifies fallback;
6. never downgrade security;
7. executor retains M1 resumable chunk/journal behavior.

Every completed transfer feeds a new directional edge observation back into BRG.

### 6.3 Resilience NBO v0

Question:

> Does the actual replica state still satisfy the Bay policy, and if not, what repair plan should be created?

Inputs:

- desired replica count;
- observed healthy replicas;
- node liveness;
- offline duration;
- fragment verification state;
- eligible replacement nodes;
- Bay repair grace policy.

States:

```text
HEALTHY
DEGRADED
REPAIR_PENDING
REPAIRING
UNAVAILABLE
LOST
```

`OFFLINE` is not equivalent to `LOST`.

Version 0 workflow:

```text
replica unavailable
   ↓
mark observed state
   ↓
wait configured repair grace
   ↓
still below desired replicas?
   ↓
Placement NBO chooses destination
   ↓
DT-NBO chooses healthy source/path
   ↓
executor copies encrypted fragment
   ↓
verify
   ↓
atomic matrix update
   ↓
state returns HEALTHY
```

If no eligible replacement exists, remain `DEGRADED` with an actionable reason instead of deleting or pretending to be repaired.

## 7. NBO composition

Do not duplicate decision logic.

- Resilience NBO calls Placement NBO for a replacement destination.
- Resilience NBO calls DT-NBO for source/path.
- Location-independent retrieval calls DT-NBO for each required fragment/source.
- Bay/storage services call Placement NBO for initial replica placement.

## 8. Privacy and security

BRG/NBO telemetry should normally use opaque IDs and operational measurements.

Record:

- Node ID;
- fragment ID;
- byte counts;
- durations;
- status;
- transport;
- hashes/verification results where necessary.

Do not record for optimisation:

- plaintext file contents;
- arbitrary source paths;
- private keys;
- bearer tokens;
- invite codes;
- relay tickets;
- unnecessary user-visible filenames.

All remote BRG submissions are authenticated/signed and bounded.

## 9. Determinism and explainability

M2 NBOs must be reproducible.

Given the same:

- BRG snapshot/version;
- policy;
- candidate set;
- optimizer version;

the decision should be deterministic unless a documented tie-breaker is required.

Use a stable tie-breaker such as Node ID ordering; do not use randomness in acceptance tests.

Expose:

```text
barn nbo decision <DECISION_ID>
barn nbo decisions
```

and machine-readable `--json` equivalents.

Operators should be able to inspect why a node was selected or rejected.

## 10. Deferred NBOs

Do not implement in `0.2.0a1`:

- Capacity/Rebalancing NBO;
- Integrity/Scrub NBO;
- Compute NBO;
- GPU/AI Model NBO;
- Federation NBO;
- Economic NBO;
- Trust NBO as an independent scoring authority;
- ML-based adaptive weight tuning.

M2 may collect the measurements needed for those later systems.
