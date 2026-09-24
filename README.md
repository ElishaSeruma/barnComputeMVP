# barnCompute

`barnCompute` is planned as a private, authenticated device group (a "Barn") for
securely exchanging explicitly shared files between a macOS computer and a
Windows computer. One host runs the Barn coordinator and may also run a normal
node agent. Each participating computer has its own durable node identity and
managed file store.

This repository is currently at the planning stage. The implementation and the
cross-platform acceptance tests described below have **not** been completed.

## M1 goal

Milestone 1 will provide a Python package with:

- Distribution name: `barnCompute`
- Import name: `barn_compute`
- Command-line program: `barn`
- Supported Python versions: 3.11 and 3.12
- Initial release candidate: `0.1.0a1` on TestPyPI only

The completed M1 must let two explicitly enrolled devices:

1. Join the same Barn through coordinator approval and verified trust
   bootstrap.
2. Report authenticated health and reachability information.
3. Import files into private, immutable managed storage.
4. Create recipient-specific, expiring read shares.
5. Transfer files directly between nodes when possible.
6. Fall back to an explicitly configured, independently deployed relay when
   public Wi-Fi prevents direct peer connections.
7. Resume interrupted transfers from already verified 1 MiB chunks.
8. Verify each chunk and the final file with SHA-256.
9. Preserve identities, metadata, files, and transfer journals across restarts.

## Effective architecture

```text
macOS: coordinator + node agent --- authenticated peer HTTPS --- Windows node
              |                              preferred
              +--- outbound WSS/TLS :443 --- relay --- WSS/TLS :443 ---+
                                      optional fallback                  |
                                      (opaque inner session) ------------+
```

The coordinator is the authority for Barn membership, node revocation, file
metadata, shares, transfer grants, and current node endpoints. It does not store
or forward managed file contents during direct transfers.

Each node agent owns its managed files and exposes an authenticated HTTPS peer
endpoint. The local CLI communicates with its node agent over a loopback-only
control API protected by a private per-user bearer token. Coordinator
administration also uses a separate loopback-only API.

Direct peer HTTPS is the preferred transport. With transport mode `auto`, a
short, bounded direct attempt may fall back to a configured relay. Modes
`direct` and `relay` will allow an operator to require one path. A relay is a
separate service that must be deliberately deployed on a public HTTPS/WSS
endpoint, normally TCP 443; installing the Python package cannot create a public
relay by itself.

The relay may route bounded logical streams only between permitted Barn peers.
It must not receive plaintext file bytes, node private keys, local-admin
credentials, or authority to approve nodes or shares. The actual Barn endpoints
must retain end-to-end authenticated encryption inside the relay tunnel. A relay
ticket controls relay admission only and never replaces node approval or a
coordinator-issued file grant.

## Security requirements

M1 is designed to fail closed. The implementation must include:

- A per-Barn certificate authority and verified TLS certificates with correct
  hostname or IP SANs.
- A separate coordinator Ed25519 key for narrowly scoped transfer grants.
- Durable Ed25519 identities for nodes, generated and retained locally.
- One-use, expiring enrolment invitations followed by explicit coordinator
  approval.
- Signed, versioned requests with timestamp, nonce, body digest, replay
  protection, clock-skew checks, and unambiguous canonicalisation.
- Recipient-, source-, file-, share-, and transfer-bound read grants with expiry
  and revocation checks.
- Loopback-only local administration, private state permissions, secret
  redaction, bounded requests, rate limits, and structured safe errors.
- Strict path confinement, symlink/reparse-point protection, quota checks,
  no-clobber exports, bounded memory and disk use, and no automatic execution of
  received files.
- No plaintext downgrade, disabled certificate validation, firewall shutdown,
  automatic router port forwarding, unknown third-party relay, or secrets in
  commands, URLs, logs, diagnostics, source control, or package artifacts.

The coordinator is a trusted administrative authority in M1. Encryption of
node files at rest and confidentiality from a compromised coordinator are not
M1 promises.

## File and transfer model

`barn file add` will copy a regular local file into a node's managed store using
a private staging file, then create an immutable manifest from that staged copy.
The default maximum file size is 512 MiB and the transport chunk size is 1 MiB.
Zero-byte files are valid.

A share is explicit, read-only, addressed to one approved node, and has a
limited lifetime. Fetching a share creates a separate short-lived transfer
grant. Every chunk request must authenticate the recipient and present the
correct grant. Verified chunks are written and journaled durably before being
accepted. After all chunks are present, the receiver assembles a temporary file,
checks its byte count and full SHA-256, commits a managed copy, and exports it
without overwriting an existing destination by default.

The same file ID, immutable manifest, share and transfer IDs, chunk hashes,
journal, authorisation rules, and final checksum apply on direct and relay
transports. A path change during transfer must reuse verified chunks rather than
restart the whole file.

## Planned CLI workflow

The exact help text will be generated by the implementation, but the intended
operator flow is:

```text
barn coordinator init --name LabBarn --advertise <MAC_IP_OR_HOST>
barn coordinator ca export --output ./barn-ca.pem
barn coordinator start --bind 0.0.0.0 --port 8443
barn coordinator invite --ttl 10m

barn node init --name <NODE_NAME> --advertise <NODE_IP_OR_HOST> --peer-port 8445
barn node enroll --coordinator https://<COORDINATOR>:8443 --ca-cert <CA_FILE> --code <CODE>
barn coordinator enrolments
barn coordinator approve <REQUEST_ID>
barn node start --bind 0.0.0.0 --peer-port 8445

barn nodes
barn doctor
barn file add <LOCAL_FILE>
barn share create <FILE_ID> --to <NODE_ID> --ttl 30m
barn share inbox
barn share fetch <SHARE_ID> --output <LOCAL_DESTINATION>
barn transfer status <TRANSFER_ID>
```

Relay-related interfaces are expected to include equivalents of:

```text
barn relay serve --config <PATH>
barn config set relay.url wss://<RELAY_DOMAIN>/v1/tunnel
barn config set transport.mode auto
```

`barn status`, `barn doctor`, heartbeat diagnostics, and transfer progress must
show whether the active path is direct or relay. Diagnostics must distinguish
direct reachability from relay connectivity and report captive-portal, DNS,
TLS, WSS, registration, and inner peer-identity failures without printing
secrets.

## Implementation plan

Work should proceed in independently testable stages:

1. Establish the `src/` Python package, `pyproject.toml`, versioned CLI, typed
   errors and models, state-directory handling, tests, and Windows/macOS CI.
2. Implement configuration, safe persistence, migrations, key and certificate
   management, request signing, replay protection, and trust bootstrap.
3. Implement coordinator administration, invitations, pending enrolments,
   explicit approval, node registry, revocation, and audit events.
4. Implement node lifecycle, authenticated heartbeat/reconnect behavior,
   persistence, reachability state, registry refresh, and `barn doctor`.
5. Implement immutable file import, manifests, recipient-scoped shares,
   transfer sessions, peer HTTPS, and grant validation.
6. Implement bounded streaming downloads, durable chunk journals, integrity
   checks, cancellation, resumption, safe final assembly, and export.
7. Implement the separately deployable WSS relay, admission tickets,
   multiplexing, quotas, flow control, inner end-to-end authenticated sessions,
   transport selection, failover, and relay-specific diagnostics.
8. Add unit, integration, security, packaging, and local multi-process tests;
   write protocol, architecture, operations, and test-report documentation.
9. Build wheel and source distributions, inspect their contents, run
   `twine check`, and prepare the TestPyPI release candidate.
10. After explicit owner authorisation, publish to TestPyPI and execute the full
    physical macOS-to-Windows and Windows-to-macOS acceptance runbook using the
    same released artifact on both machines.

If secure relay tunnelling cannot be completed in this iteration, the direct
implementation must remain usable and the public-Wi-Fi feature must be marked
**NOT IMPLEMENTED / NOT TESTED**. It must not be replaced by an insecure tunnel.

## Verification and release gates

Automated coverage must include cryptographic vectors, canonical request
signing, timestamp and replay rejection, invitation lifecycle, approval and
revocation, TLS CA/SAN failures, authorisation boundaries, unsafe paths,
malformed manifests, edge-case file sizes, chunk corruption and short reads,
restart/resume, no-clobber exports, database migrations, cross-platform paths,
and package contents. A deterministic 100 MiB fixture will be used for transfer
and memory tests.

Physical acceptance requires clean Python 3.11 or 3.12 environments on macOS
and Windows. Runtime dependencies are installed separately from production
PyPI; `barnCompute` itself is then installed from TestPyPI with the explicit
TestPyPI index and `--no-deps`. Local editable installs or locally built wheels
do not count as this acceptance test.

The acceptance run must prove:

- Persistent identities and state across coordinator and agent restarts.
- Correct `ONLINE`, `SUSPECT`, `OFFLINE`, and `REVOKED` behavior.
- Rejection of pending, forged, replayed, expired, revoked, and wrong-recipient
  access.
- Correct manifests for 0-byte, 1-byte, and 1 MiB boundary cases.
- Successful 100 MiB transfers in both directions with matching SHA-256 values.
- Safe interruption and resume without re-downloading verified chunks.
- Direct operation on a trusted LAN.
- Relay operation through a real deployed relay while inbound cross-device
  traffic is blocked, including relay outage and direct-to-relay failover.
- Bounded concurrency, memory, disk usage, and clean cancellation behavior.

All results must be recorded as `PASS`, `FAIL`, or `NOT RUN` with real evidence
in `docs/test-report.md`. Tests requiring credentials, a deployed relay, or two
physical machines remain `NOT RUN` until they actually happen.

Publishing is limited to TestPyPI for M1. It requires a separate TestPyPI
account, an owner-selected license, confirmation that the package name is
available, explicit owner authorisation, and securely configured credentials.
Production PyPI publication is a separate future decision.

## Out of scope

M1 does not include distributed fragment placement, erasure coding, redundant
availability after the source is lost, multi-Barn federation, mobile agents,
compute orchestration, public download links, automatic filesystem-wide
sharing, or M2's Bay and replica model. Public-Wi-Fi support is limited to the
explicitly configured secure relay path; it is not a promise to bypass captive
portals or network policy.

M2 design begins only after the M1 TestPyPI and physical cross-platform evidence
has been reviewed.
