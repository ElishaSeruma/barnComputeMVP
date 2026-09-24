# Protocol v1

Status: partial. This document records the implemented signed-request envelope;
service routes and grant canonicalisation will be added with their code.

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

