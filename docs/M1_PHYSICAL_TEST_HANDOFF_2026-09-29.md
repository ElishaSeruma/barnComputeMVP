# M1 physical acceptance handoff - 2026-09-29

## Purpose

Continue M1 physical acceptance for barnCompute 0.1.0a1 on a Mac and Windows
machine connected to the same phone hotspot. Do not start M2 or mark M1 accepted
from local automated tests alone. Use `docs/M1_ACCEPTANCE_RUNBOOK.md` for the
full checklist, and record actual PASS/FAIL/NOT RUN evidence in
`docs/test-report.md` or a dated result file. This handoff is a current-state
correction, not evidence that physical transfer has passed.

## Verified state

- Repository main was at `072ac4c` when this handoff was written. That commit
  corrected release metadata; `842bc31` contained the integrated runtime.
- TestPyPI `barnCompute==0.1.0a1` was published. Its public release JSON showed
  a wheel SHA-256 of
  `f1cbc28f916749b15cc46a2e5ab7760ad27d9693153c76e36ec2d070f85acd86`
  and sdist SHA-256 of
  `ab32556fa838cb3ed886d77f409a3edefd39550a0ec0f6cfa3c847087378c8b9`.
  Both matched the locally screened artifacts at publication time.
- Mac terminal evidence shows Python 3.12, production-PyPI runtime dependencies,
  and the TestPyPI wheel installed in a new venv; its `barn --version` reported
  `0.1.0a1`. The user reports the same version on Windows. Preserve the install
  logs and independently verify Windows release provenance before marking the
  two-host package gate PASS.
- Earlier local automation passed 82 tests on each platform at 82% coverage.
  These are local logical-node tests, not two-machine transfer evidence.
- Hotspot IPs: Mac `172.20.10.3`; Windows Wi-Fi `172.20.10.10`.
  Windows pinged the Mac successfully twice. TCP 8443 has not been tested.
- No coordinator, nodes, shares, physical transfers, or public relay have been
  confirmed started or tested in this physical run.

## What went wrong on the Mac

The Mac prompt was `~ %` when the user ran `python3.12 -m venv
.venv-m1-release`. Thus the release environment is
`/Users/elisha/.venv-m1-release`, **not** inside
`/Users/elisha/Developer/barnTest`. The successful install and version command
used `./.venv-m1-release/bin/barn` while the working directory was `~`.
Plain `barn --version` failed because the venv's `bin` is not on the shell PATH.

The user then changed into `/Users/elisha/Developer/barnTest`, which `ls` and
`tree` showed was empty, and tried `./.venv-m1-release/bin/barn` there. All four
commands failed with `zsh: no such file or directory`. This is a working-
directory/path error in the previous guidance, not evidence of a package or
Mac runtime defect. None of those coordinator commands executed, so do not
assume the coordinator state or CA certificate exists. Do not reinstall or
delete the working venv just to correct this path. Do not use the development
checkout's editable `barn` for physical release-provenance testing.

## Exact next step on Mac

Run these from any working directory; the executable and state paths are
absolute. Use fresh state only if `coordinator init` succeeds. If it says state
already exists, inspect before any destructive action.

```sh
BARN="$HOME/.venv-m1-release/bin/barn"
COORD="$HOME/barncompute-m1-coordinator"
"$BARN" --version
"$BARN" coordinator init --name LabBarn --advertise 172.20.10.3 --state-dir "$COORD"
"$BARN" coordinator ca export --output "$HOME/barncompute-m1-ca.pem" --state-dir "$COORD"
"$BARN" coordinator start --bind 0.0.0.0 --port 8443 --state-dir "$COORD"
```

Record the CA SHA-256 fingerprint printed by export. Keep the final foreground
command running. If macOS Firewall prompts, allow this specific incoming
Python service, not a blanket firewall disable. From Windows PowerShell test:

```powershell
Test-NetConnection 172.20.10.3 -Port 8443
```

Stop and diagnose if `TcpTestSucceeded` is not `True`. A successful ping alone
does not prove that TCP 8443, TLS, enrolment, or peer traffic works. Do not
paste private keys, admin tokens, TestPyPI tokens, or invitation codes into a
chat or commit them. The exported CA certificate and its fingerprint are public.

## Remaining sequence after TCP 8443 succeeds

1. Verify the CA fingerprint independently on both hosts and copy only the
   public CA certificate to Windows. Keep coordinator and node state separate.
2. Initialize a Mac node advertised at `172.20.10.3` and a Windows node
   advertised at `172.20.10.10`; use the **TestPyPI-installed** `barn` executable
   on each host. Create separate one-use invitations on the Mac, enrol each
   node with `--ca-cert` and `--ca-fingerprint`, review identity fingerprints,
   explicitly approve, poll enrolment status, and start both agents. Keep the
   Mac coordinator and both node agents running in separate terminals.
3. Verify heartbeat/registry and direct peer port 8445 in both directions.
   Certificate SANs are tied to advertised hotspot IPs; if addresses change,
   do not blindly reuse the old identities or bypass TLS verification.
4. Import and share a deterministic 100 MiB file, fetch it direct Mac to
   Windows and Windows to Mac, and compare source/destination SHA-256. Test
   0-byte, 1-byte, 1 MiB, and 1 MiB+1-byte boundaries, no-clobber exports,
   restart/resume, cancellation, corrupt/missing chunk repair, grant/share/node
   revocation, and resource use. Use disposable state for irreversible revoke.
5. Public WSS relay tests are **not yet possible** with the present setup:
   the owner has no relay server/domain/TLS certificate. Later provide those
   plus verified HTTPS reachability to the coordinator from both nodes; run
   forced relay, blocked-direct auto fallback, outage/recovery, and 100 MiB
   both-direction tests without disabling certificate verification.
6. Update the acceptance report only with observed evidence. TestPyPI upload
   and local suite pass do not by themselves complete M1.

## Instructions for a fresh chat

Read this file, `docs/M1_ACCEPTANCE_RUNBOOK.md`, and the pasted Mac terminal
output. Start by correcting the executable path to
`$HOME/.venv-m1-release/bin/barn` and getting the Mac coordinator online.
Guide one checkpoint at a time using actual output. Do not assume `barnTest`
contains the venv, that `barn` is globally installed, that coordinator init
succeeded, or that M1 is accepted. Prefer read-only diagnosis before changing
state; never delete existing private state or expose credentials.
