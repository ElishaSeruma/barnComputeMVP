# barnCompute M1 Closure and Acceptance Gate

## Status

This document closes the remaining gap between the implemented `0.1.0a1` M1 runtime and an evidence-backed M1 acceptance verdict.

It does **not** redefine M1. It reconciles the original M1 requirements with the current implementation and the physical results recorded on 2026-09-29.

## Evidence already established

The current M1 evidence demonstrates, on physical macOS and Windows hosts:

- same `0.1.0a1` CLI version on both hosts;
- installed package contents matching the published TestPyPI wheel contents;
- coordinator CA fingerprint agreement;
- coordinator TCP reachability on the test network;
- explicit node enrolment and approval;
- both nodes ONLINE in the registry;
- direct peer TCP reachability;
- 100 MiB Mac→Windows transfer with matching SHA-256;
- 100 MiB Windows→Mac transfer with matching SHA-256 after one transient initial failure;
- 0-byte, 1-byte, 1 MiB and 1 MiB+1 boundary transfers;
- no-clobber destination behavior;
- missing-chunk and corrupt-chunk repair;
- share expiry, revocation and wrong-recipient denial;
- disposable node revocation;
- interrupted transfer persistence across coordinator/node restart;
- cancellation during incomplete transfer followed by successful resume;
- concurrent bidirectional direct transfers.

Do not rerun passed destructive tests merely to create prettier evidence unless required by a changed artifact.

## Remaining closure gates

### C1 — Reconcile repository acceptance documentation

The repository contains older status text that predates the physical run. Update the canonical acceptance record without deleting historical checkpoint files.

Required:

- `docs/test-report.md` must reflect the real TestPyPI publication and physical direct-transfer evidence.
- `docs/next-steps.md` must no longer claim that all physical transfers or TestPyPI publication are unrun.
- Preserve dated historical files unchanged where possible.
- Link the 2026-09-29 physical-results file as evidence.
- Record any later closure run in a new dated file.

Pass condition: one canonical report accurately separates PASS, FAIL, INCOMPLETE and NOT RUN items.

### C2 — TestPyPI installation provenance

The installed environments were shown to be byte-equivalent to the published TestPyPI wheel, but the original pip download/install logs were not retained.

Perform a fresh clean installation on both hosts:

1. Create a new isolated Python 3.11 or 3.12 environment.
2. Install runtime dependencies from production PyPI in a separate step.
3. Install **only** `barnCompute==0.1.0a1` from TestPyPI with `--no-deps`.
4. Preserve a redacted installer log showing the TestPyPI artifact source.
5. Download the wheel separately from TestPyPI and record SHA-256.
6. Confirm the installed package files correspond to that wheel.
7. Run `barn --version`, `pip check`, and a minimal coordinator/node smoke test.

Do not publish a replacement artifact under the same version. TestPyPI artifacts are immutable.

Pass condition: Mac and Windows each have traceable, redacted proof that the tested M1 package came from the same TestPyPI `0.1.0a1` release.

### C3 — Synchronized resource observation

The physical run captured useful post-transfer resource snapshots, but not synchronized peak observations during concurrent transfer.

Capture during at least one overlapping bidirectional 100 MiB transfer:

- process RSS/working set for coordinator and node agents;
- free disk before, during and after;
- node-state/transfer-journal disk consumption;
- elapsed time;
- transport path;
- transfer SHA-256 result;
- unexpected memory growth or leaked temporary files.

This is an observation gate, not a performance guarantee.

Pass condition: the report contains synchronized measurements and no unbounded resource-growth defect is observed.

### C4 — Public relay deployment

Deploy the relay on an owner-controlled or explicitly approved host:

- public DNS name;
- valid TLS certificate;
- TCP 443/WSS;
- only the public coordinator grant key plus relay TLS material;
- no Barn CA private key;
- no node private keys;
- no coordinator admin token;
- bounded sessions/frames/bytes and safe logs.

Validate:

- forced relay Mac→Windows 100 MiB;
- forced relay Windows→Mac 100 MiB;
- SHA-256 equality;
- relay interruption/recovery;
- relay revocation behavior;
- direct→relay resume with already verified chunks reused;
- relay outage fails closed;
- invalid/expired ticket denied;
- wrong peer/Barn denied;
- relay cannot read plaintext file payload.

### C5 — Public-Wi-Fi control-plane gap

This is a closure blocker derived from a mismatch between the original public-Wi-Fi fallback requirement and the present M1 runtime.

The original fallback design requires the coordinator and nodes to be able to establish outbound relay connectivity on client-isolated networks. The current runtime relays peer file data but still requires nodes to reach coordinator HTTPS directly for membership/share/grant/revocation checks.

That means a public network can allow outbound WSS to the relay while still preventing a Windows node from reaching a Mac-hosted coordinator on the same isolated Wi-Fi.

M1 must not claim complete built-in public-Wi-Fi fallback until this is resolved.

#### Required M1 closure behavior

Provide an outbound-only, authenticated coordinator control path through the relay/rendezvous infrastructure without making the relay a Barn authority.

Preferred architecture:

```text
Mac coordinator
    │ outbound WSS/TLS
    ▼
Public relay/rendezvous
    ▲
    │ outbound WSS/TLS
Windows node

Inside the tunnel:
- coordinator identity remains authoritative;
- node signed requests remain mandatory;
- coordinator responses remain authenticated;
- relay does not receive admin authority;
- relay cannot mint membership, shares or grants;
- certificate/signature verification is never disabled.
```

Acceptable implementation options include:

- multiplexing coordinator control RPC streams over the existing encrypted relay framework; or
- a dedicated coordinator outbound-tunnel service using the same trust principles.

Do **not** solve this with plaintext HTTP, disabled TLS verification, UPnP, router port forwarding, blanket firewall disabling, or an unknown third-party tunnel.

#### Required physical test

Simulate actual client isolation:

- no inbound cross-device Mac↔Windows connectivity;
- both hosts retain outbound TCP 443;
- neither node can reach the coordinator's LAN listener directly;
- both can reach the public relay.

Prove:

- approved nodes can maintain/restore coordinator control connectivity;
- heartbeat/registry works through the fallback control path;
- share/grant/revocation operations work;
- 100 MiB file transfer succeeds via relay;
- revoked node/share is denied;
- coordinator and relay outage errors are distinguishable;
- recovery works after connectivity returns.

Pass condition: Barn remains operable for its required M1 control and data operations without direct cross-device LAN reachability.

## Known non-blocking observation

A Windows→Mac direct transfer initially failed once and passed on retry; the physical record did not establish the cause. Keep this as a known observation. If it reproduces, open a tracked issue with logs and correlation IDs. Do not invent a root cause.

## M1 closure verdict

Mark M1 `ACCEPTED` only when C1–C5 are complete and the canonical report contains real evidence.

M1 acceptance does **not** mean:

- production PyPI release;
- distributed fragment storage;
- Bay semantics;
- erasure coding;
- compute orchestration;
- BALL/EDHE;
- federation.

## Gate into the M2 release candidate

M2 implementation may be developed while C2–C5 external testing is arranged, provided M1 regressions remain covered. However `barnCompute==0.2.0a1` must not be presented as the first accepted M2 release candidate until the inherited M1 network/security substrate used by M2 has passed closure.
