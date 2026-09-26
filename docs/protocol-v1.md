# Protocol v1

Status: partial. Enrolment HTTP routes and the signed-request envelope are
implemented; heartbeat and registry routes, local immutable file import, and
share/grant authority and grant-authenticated peer manifest/chunk routes are
implemented; durable recipient transfer journals, resume, assembly, and safe
export, authenticated share control-plane routes, live download orchestration,
and fail-closed transport selection are implemented; signed WSS relay
admission and an encrypted inner-session envelope are implemented. The inner
hello now binds the ephemeral key to the node identity and transcript; relay
production deployment and physical acceptance remain pending. The live relay
transport, signed remote share APIs, recipient proof, and automatic fallback
are now integrated; see the current runtime details below.

## Integrated M1 runtime

All `/v1/shares` and relay-ticket routes require the versioned Ed25519 signed
request headers and durable nonce validation, using the node's enrolled key.
Sources create and revoke their own shares; recipients obtain their own grants.
Node agents perform coordinator validation on every manifest/chunk delivery,
failing closed when current membership/share status cannot be checked.

- `POST /v1/shares`: source-bound creation.
- `GET /v1/shares`: only source/recipient shares.
- `POST /v1/shares/{share_id}/grant`: recipient-bound authority.
- `POST /v1/shares/{share_id}/revoke`: source-only revocation.
- `POST /v1/grants/validate`: current membership/share validation.
- `GET /v1/nodes/{peer_id}/identity`: authenticated enrolled public identity.
- `POST /v1/shares/{share_id}/relay-ticket`: recipient requests a pair ticket.
- `GET /v1/relay/tickets`: source retrieves its pending relay sessions.

Direct manifest/chunk requests require the grant plus a signed recipient
request. Signatures bind method/path/timestamp/nonce/body; the grant recipient
must match the signer. TLS CA/SAN validation is mandatory, and the responding
node certificate's UUID must match the granted source.

Relay tickets additionally sign both peers' enrolled public identity keys.
Admission starts with a fresh random relay challenge; the joining node signs
`barn-relay-admission-v1`, ticket UUID, node UUID, and challenge separated by
newlines (no trailing newline). Possessing a ticket alone cannot impersonate
a peer. Connections pair only within the same ticket UUID, and duplicate
connections are refused. Frames may target only the opposite ticket peer.

The recipient sends an identity-signed X25519 hello bound to the complete
ticket. The source signs its fresh ephemeral key with the ticket and recipient
ephemeral key. HKDF-SHA256 derives two distinct 32-byte direction keys over the
ticket and both ephemeral keys. ChaCha20-Poly1305 authenticates the ticket and
each direction's monotonically increasing message counter as associated data.
Replays, wrong directions, altered identities, and modified frames fail closed.
The relay sees opaque envelopes and never sees grants or file plaintext.

Logical packets use a four-byte big-endian length and bounded 64 KiB relay
frames. Packet buffers cannot exceed 2 MiB plus one frame. Sources allow eight
workers; relay sockets are limited to 64 admitted connections, 1 MiB decoded
frames, 768 MiB bytes per socket, five-minute ticket expiry, and bounded waits.
The WebSocket server caps raw messages to 2 MiB and its receive queue to four.

Grant renewal uses the immutable share UUID as transfer UUID. Journals are
revalidated before download skips committed chunks; missing/corrupt chunks
are fetched again. Cancellation retains the journal, and resume re-enables it.
Export uses atomic hard-link publication so a concurrent destination creation
cannot be overwritten. Both transports preserve manifest and journal rules.
HTTP bodies are bounded while streaming, including absent Content-Length;
each origin is rate-limited to 1200 requests per minute.

Coordinator schema migration installs transactional audit triggers for invite
creation, enrollment decisions, share creation/revocation and node revocation.
Only time, operation, subject UUID and outcome are returned by the token-protected
`GET /local/v1/audit`; secret material is never included. The admin client
requires a literal loopback HTTP IP and rejects credentials/query fragments.

## Enrolment HTTP routes

The coordinator public listener uses HTTPS with its Barn-CA-issued certificate:

- `GET /v1/health`
- `POST /v1/enrolments/challenge`
- `POST /v1/enrolments`
- `GET /v1/enrolments/{request_id}` with `X-Barn-Enrolment-Receipt`

The separate coordinator administration listener is hard-bound to
`127.0.0.1`, requires its private bearer token, and exposes status, invitation
creation, pending listing, approval, and rejection below `/local/v1`. The node
uses the same loopback-only pattern for local status. JSON requests are bounded
to 64 KiB and errors use a structured envelope without echoing secrets.

## Signed request canonicalisation

The Ed25519 signing input is UTF-8 and has no trailing newline:

```text
barn-request-v1\n
<UPPERCASE METHOD>\n
<NORMALISED PATH AND SORTED QUERY>\n
<RFC3339 TIMESTAMP>\n
<RANDOM NONCE>\n
<LOWERCASE SHA256 BODY HEX>
```

The path is percent-encoded while preserving valid path separators. Query pairs
are parsed with blank values retained, sorted by key and value, and encoded
again. GET requests hash the empty body. Fields containing CR or LF are
rejected. Signatures use unpadded base64url.

An authenticated endpoint verifies timestamp skew before signature validation,
then records the `(node_id, nonce)` pair in SQLite. Duplicate pairs within the
acceptance window are rejected even after a process restart.

## Enrolment proof canonicalisation

The node identity key signs this UTF-8 input without a trailing newline:

```text
barn-enrolment-proof-v1\n
<CHALLENGE>\n
<NODE UUID>\n
<LOWERCASE SHA256 CSR PEM HEX>\n
<ADVERTISED HOST>\n
<PEER PORT>\n
<PROTOCOL VERSION>
```

CR and LF are forbidden inside fields. The coordinator verifies this signature
and independently verifies the CSR signature. The CSR organizational unit must
equal the Node ID, its common name must equal the node name, and its single SAN
must exactly equal the advertised IP address or DNS name.

Challenges are random, short-lived, stored only as SHA-256 digests, and bound to
one invitation and Node ID. Request-specific polling receipts are also stored
only as digests. A valid request remains pending until explicit approval.

The issued node certificate contains CA-signed private extensions:

- `1.3.6.1.4.1.62187.1.1`: UTF-8 Barn UUID.
- `1.3.6.1.4.1.62187.1.2`: raw 32-byte coordinator grant public key.

These bind the grant verification key to the pinned Barn trust root. Binary
protocol values are unpadded base64url in JSON. The node client requires an
explicit CA file, refuses plaintext coordinator URLs, and disables redirects.
