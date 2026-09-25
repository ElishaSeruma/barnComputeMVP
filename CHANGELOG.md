# Changelog

## 0.1.0a1 - Unreleased

- Establish the M1 package, CLI, security primitives, and test foundation.
- Add atomic coordinator initialization, Barn CA and server identity creation,
  public CA export, SQLite migrations, and hashed expiring invitations.
- Add durable node identity and TLS CSR state, pinned CA trust bootstrap,
  challenge-bound enrolment proofs, pending approval, rejection, transactional
  certificate issuance, receipt polling, and schema v2 migration.
- Prevent expected CLI errors from leaking Python tracebacks.
