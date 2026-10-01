# Changelog

## 0.1.0a2 - Unreleased

- Remove completed-transfer assembly files on success and every export failure.
- Add coordinator-signed node control grants and an authenticated outbound WSS
  coordinator control tunnel with end-to-end encrypted RPC payloads.
- Preserve existing signed requests, nonce replay protection, coordinator
  authority and live revocation checks across direct and relayed control paths.

## 0.1.0a1 - 2026-09-29 (TestPyPI)

- Integrate member-signed remote shares, recipient proof and current revocation
  checks into direct file delivery without sharing coordinator admin tokens.
- Add deployable WSS relay, identity challenge admission, authenticated
  ephemeral sessions, direction keys, replay protection, bounded frames and
  automatic direct-to-relay fallback.
- Preserve transfer identity across grant renewal, repair corrupt/missing
  resumed chunks, add cancellation/status/resume commands, retain received
  managed copies, and publish exports without overwriting concurrent files.
- Add real TLS/WSS acceptance tests, deterministic 100 MiB fixtures, shutdown
  regression tests, package archive screening and the M1 Mac/physical runbook.

- Establish the M1 package, CLI, security primitives, and test foundation.
- Add atomic coordinator initialization, Barn CA and server identity creation,
  public CA export, SQLite migrations, and hashed expiring invitations.
- Add durable node identity and TLS CSR state, pinned CA trust bootstrap,
  challenge-bound enrolment proofs, pending approval, rejection, transactional
  certificate issuance, receipt polling, and schema v2 migration.
- Add CA-verified public HTTPS enrolment APIs, receipt-bound status polling,
  loopback-only bearer-authenticated coordinator/node administration APIs, and
  foreground coordinator/node service runners.
- Prevent expected CLI errors from leaking Python tracebacks.
