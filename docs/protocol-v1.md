# Protocol v1

Status: partial. Enrolment HTTP routes and the signed-request envelope are
implemented; heartbeat and registry routes, local immutable file import, and
share/grant authority and grant-authenticated peer manifest/chunk routes are
implemented; durable recipient transfer journals, resume, assembly, and safe
export, authenticated share control-plane routes, and live download
orchestration are implemented; relay routes remain pending.

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
