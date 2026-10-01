# M1 C5 outbound coordinator control path - 2026-10-01

## Verdict

**SOURCE IMPLEMENTED; LOCAL AUTOMATION PASS; PHYSICAL C5 NOT RUN.**

The unpublished `barnCompute==0.1.0a2` correction candidate implements the
outbound-only authenticated coordinator control path required by C5. Local
real-TLS/WSS integration tests prove control operations with the direct
coordinator URL unavailable. This does not close C5: the required two-device
client-isolation test still needs an approved public relay with DNS and valid
TLS on TCP 443.

## Trust and transport design

- The coordinator grant key signs a bounded control grant containing Barn ID,
  node ID, node identity public key, issue time and expiry. New approvals carry
  a grant; enrolled nodes can renew it through the signed control API.
- The relay has only the public grant key and its TLS material. It authenticates
  the coordinator by a fresh challenge signed with the grant key and a node by
  its signed control grant plus a fresh identity-key proof.
- The coordinator maintains an outbound WSS connection at
  `/v1/control/coordinator`; nodes use outbound WSS at `/v1/control/node`.
- Each node session performs an ephemeral X25519 handshake. The node hello is
  signed by the node identity key, the coordinator hello by the grant key, and
  HKDF-derived directional ChaCha20-Poly1305 keys protect RPC frames.
- The relay routes bounded opaque frames by random session ID. It receives no
  coordinator admin token, Barn CA private key or node private key and cannot
  decrypt or mint coordinator operations.
- Decrypted requests are dispatched into the existing coordinator FastAPI app.
  Existing node request signatures, nonce replay checks, membership/share/grant
  authority and live revocation checks therefore remain mandatory.
- Direct verified HTTPS remains preferred. After a direct transport failure,
  the client reuses the authenticated control session; if it fails, direct
  connectivity is tried again before a new relay session is established.

## Local evidence

The local isolation tests use a real TLS/WSS relay and deliberately point node
clients at a closed direct coordinator port. They prove:

- approval-time and startup control-grant provisioning;
- heartbeat and registry refresh through the control tunnel;
- share creation, grant issuance and share revocation;
- revoked-node denial by the coordinator, not merely relay admission;
- distinguishable coordinator-control and relay-connectivity failures;
- successful control recovery after the coordinator tunnel reconnects.

Completed Windows verification for the combined C3 cleanup and C5 change:

- Ruff: PASS.
- Full suite: 84 passed, zero failures/skips, one known Starlette deprecation
  warning, 363.23 seconds.
- Coverage: 82% (2,603 of 3,167 statements covered).
- JUnit: ignored local evidence `local-state/m1-a2-2026-10-01.xml`.
- Coverage data: ignored local evidence
  `local-state/.coverage-m1-a2-2026-10-01`.

A later exact-source rerun encountered Windows host memory exhaustion during
real-WSS startup; the retained limitation and preceding partial result are
recorded in the [C3 resource record](M1_C3_RESOURCE_RESULTS_2026-10-01.md).

## Candidate artifact

The candidate is not published and is not accepted M1 evidence yet.

- Wheel: `dist/barncompute-0.1.0a2-py3-none-any.whl`
- Wheel SHA-256: `eb27cfcc301cbf4272b16139383f97ce779b13876c7b9d6722b3e1d3f06fcd99`
- Sdist: `dist/barncompute-0.1.0a2.tar.gz`
- Build, Twine checks and archive screening: PASS.
- Fresh Windows wheel environment with production dependencies: `pip check`
  PASS, version `0.1.0a2`, import resolved from that environment's
  `site-packages`.

## Remaining physical evidence

After an owner-approved relay host exists, run C4 and C5 with both hosts able
to reach outbound TCP 443 but unable to make any direct cross-device connection.
Record control recovery, heartbeat/registry, share/grant/revocation, a 100 MiB
relay transfer, revoked node/share denial, relay/coordinator outages and
recovery. Until that evidence exists, C5 remains incomplete and M1 remains not
accepted.
