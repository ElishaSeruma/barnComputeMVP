# M1 architecture

Status: implemented development runtime; public deployment and released
physical acceptance remain pending. Historical foundation decisions below are
retained; current operational instructions are in `M1_ACCEPTANCE_RUNBOOK.md`.

## Live services

The coordinator public HTTPS API now carries member-signed share and relay
control requests. Each node agent refreshes heartbeat/registry and uses the
coordinator as current authority before serving a file. Direct peer requests
also require recipient signature and persistent replay protection.

For relay transfers, the recipient creates a signed pair ticket; the source
agent polls its ticket inbox and opens an outbound verified WSS connection.
An independent relay pairs the sockets by ticket UUID. Each node proves its
enrolled identity at admission, then establishes an encrypted inner session
with its peer. Bounded RPCs transport manifest/chunks with the same grants,
journals, hashes, and destination rules as direct HTTPS.

SQLite schema version 5 adds durable relay tickets without deleting existing
coordinator state. Renewal keeps a stable share/transfer UUID. Existing
pre-integration journals with random transfer UUIDs cannot automatically map
to the new stable identifier; preserve their state and fetch the share under
the new journal. The owner can archive old disposable test state after review.

Production nodes require coordinator HTTPS reachability for revocation checks,
even when file data uses relay. M1 does not implement a coordinator proxy.

## Boundaries

The coordinator owns membership, revocation, metadata, shares, transfer grants,
and audit records. Node agents own file bytes, immutable manifests, peer serving,
and transfer journals. The CLI contains no protocol or persistence business
logic. Local administrative APIs bind to loopback only.

Direct Barn-CA-verified HTTPS is the preferred data path. A configured relay is
an optional outbound-only transport. The relay carries an inner authenticated
endpoint session and therefore cannot read file content or issue Barn authority.

## Initial dependency decisions

- Pydantic supplies strict, versioned boundary models.
- `cryptography` supplies Ed25519 and X.509 primitives.
- Typer supplies the CLI contract.
- `platformdirs` selects per-user data and configuration directories.
- SQLite will provide transactional coordinator and node persistence.
- FastAPI, Uvicorn, HTTPX, and the WSS implementation will be added with their
  corresponding service stages rather than being unused runtime dependencies.

## Invariants established in the foundation

- Protocol and package versions are separate.
- Signed requests use one domain-separated canonical byte representation.
- Nonces are accepted transactionally and persist across process restarts.
- Private files use exclusive creation and per-user permissions where the host
  platform exposes POSIX modes.
- Configuration rejects unknown fields and unsupported transport modes.

## Coordinator state layout

Coordinator initialization is atomic: all files and the migrated database are
created in a private sibling staging directory, then that directory is renamed
into place. Existing state is never overwritten implicitly.

```text
coordinator/
  coordinator.json
  coordinator.db
  ca-cert.pem
  coordinator-cert.pem
  secrets/
    ca-key.pem
    coordinator-key.pem
    grant-key.pem
    admin.token
```

The CA uses an Ed25519 key and a ten-year self-signed certificate. The
coordinator uses a separate Ed25519 TLS key and a 90-day certificate whose SAN
matches the configured IP address or DNS name. Transfer grants use a third,
independent Ed25519 key. Invitation codes contain 192 random bits and only their
SHA-256 digests are persisted.

## Node identity state

Node initialization is atomic and refuses to overwrite existing state:

```text
node/
  node.json
  node.csr.pem
  trusted-ca.pem
  node-cert.pem
  barn-ca.pem
  grant-public.key
  secrets/
    identity-key.pem
    tls-key.pem
    enrolment-receipt.token
```

The node identity key signs application requests and enrolment proofs. A
separate TLS key signs the CSR and matches the issued node certificate. The
operator pins the public Barn CA by an out-of-band verified SHA-256 fingerprint
before the node can submit an enrolment request. The pending receipt is removed
after successful approval.

## Persistence-first enrolment

The current enrolment workflow is implemented in service and repository layers
without network transport:

1. Coordinator validates an active invite and issues a short-lived random
   challenge bound to the prospective Node ID.
2. Node signs a domain-separated proof containing the challenge, Node ID, CSR
   digest, advertised host, peer port, and protocol version.
3. Coordinator verifies the proof, CSR signature and subject, exact SAN,
   challenge binding, invite state, protocol major, and identity conflicts.
4. A valid request remains `AWAITING_APPROVAL`; the invite is reserved but not
   consumed.
5. Explicit approval atomically registers the node, stores the certificate,
   marks the request approved, and consumes the invitation.
6. The CA-signed certificate binds the Barn ID and coordinator grant public key
   in private extensions.
7. The node checks the pinned CA, certificate signature, TLS key, SAN, Barn ID,
   and grant-key binding before accepting the result.

Schema version 2 adds durable challenges and approval-result material while
migrating version 1 enrolment tables without deleting state. The next phase
exposes these operations through verified coordinator HTTPS and loopback-only
administration APIs.
