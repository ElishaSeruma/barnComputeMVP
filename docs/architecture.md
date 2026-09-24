# M1 architecture

Status: initial decision record; implementation is incomplete.

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

