# M1 C2 installation provenance - 2026-10-01

## Scope and verdict

Published release: `barnCompute==0.1.0a1`.
Windows C2: **PASS**. Mac C2: **PASS**, based on owner-shared terminal evidence
from the guided fresh-install, file-verification and HTTPS smoke checkpoints.
Overall C2: **PASS**. The Mac logs remain on the Mac; they were not independently
read from this Windows checkout.
M1 is not accepted; C3-C5 remain open.

This run installs the published package, not this checkout. The checkout is
based on `415786816a1b6087e2b86d947be4957e27ab99fe`, with uncommitted documentation
and a new verification script. No runtime change, migration, publication or
commit is part of this provenance checkpoint.

## Windows result

- Completion: `2026-10-01T02:27:39.756635+00:00` UTC.
- Host: Windows 11 build 26200, AMD64.
- Python: 3.12.10; pip: 25.0.1.
- Fresh environment: `local-state/m1-c2-windows-2026-10-01/venv`.
- Runtime dependencies installed separately from `https://pypi.org/simple/`.
- Only `barnCompute==0.1.0a1` installed in the TestPyPI step, with `--no-deps`,
  verbose log and pip JSON installation report.
- Separate wheel download used TestPyPI with `--no-deps --only-binary=:all:`.
- Installed package imported from the fresh environment's `site-packages`.
- All 30 wheel entries other than `RECORD` matched the installed files byte-for-byte.
- Installer report hash matched the separately downloaded wheel hash and the
  previously recorded published hash.
- `pip check`: `No broken requirements found.`
- `barn --version`: `0.1.0a1`.
- Disposable smoke: two nodes enrolled through verified coordinator HTTPS,
  explicitly approved, heartbeated, appeared in the registry, and completed a
  small direct HTTPS transfer with matching content. Test listeners stopped.
- Existing physical-test agents, environments and state were not changed.

Wheel: `barncompute-0.1.0a1-py3-none-any.whl`.
SHA-256: `f1cbc28f916749b15cc46a2e5ab7760ad27d9693153c76e36ec2d070f85acd86`.

Public artifact source:
[TestPyPI wheel](https://test-files.pythonhosted.org/packages/d1/ef/b90cec74b5518032274e36ff763f4ca6ee7d0b40dc6d0758844c5e8f3bd6/barncompute-0.1.0a1-py3-none-any.whl).

### Retained redacted installer evidence

The following excerpt was checked against the actual installation log. Only
the local output path is redacted; the public artifact URL is retained.

```text
Using pip 25.0.1 from <C2_OUTPUT>\venv\Lib\site-packages\pip (python 3.12)
Looking in indexes: https://test.pypi.org/simple/
Collecting barnCompute==0.1.0a1
Downloading https://test-files.pythonhosted.org/packages/d1/ef/b90cec74b5518032274e36ff763f4ca6ee7d0b40dc6d0758844c5e8f3bd6/barncompute-0.1.0a1-py3-none-any.whl (67 kB)
Installing collected packages: barnCompute
Successfully installed barnCompute-0.1.0a1
```

Full evidence under the ignored `local-state/m1-c2-windows-2026-10-01`:
`dependencies.redacted.log`, `testpypi-install.redacted.log`,
`testpypi-download.redacted.log`, `pip-check.redacted.log`,
`barn-version.redacted.log`, `verification.redacted.log`,
`install-report.json`, `result.json`, and the downloaded wheel.
Private disposable keys remain under `private-smoke-state`; do not publish
that directory or the entire output tree.

## Reproduction and limits

Run `scripts/verify_m1_release.py` using Python 3.11 or 3.12 and a new output
directory. It refuses an existing output directory, disables pip configuration
files and inherited pip/Python overrides for child commands, separates the
indexes, verifies hashes and installed content, then runs local smoke checks.

```powershell
.venv-heartbeat\Scripts\python.exe scripts/verify_m1_release.py --output local-state/m1-c2-windows-2026-10-01
```

The successful run used the initial script revision; subsequent edits added
path-redacted log copies and increased the subprocess timeout from 300 to 600
seconds. The final redaction helper was run over all six completed Windows logs.
These edits do not change installation or verification behavior. Ruff passed.

This is installation provenance and a minimal smoke check, not a rerun of the
full automated suite, cross-host transfer acceptance, synchronized resource
measurement or public relay acceptance. The new dependency set is whatever
production PyPI resolved within the existing release constraints; exact resolved
versions are retained in the dependency log.

## Mac result

Owner terminal evidence establishes Python 3.12.14 and working directory
`/Users/elisha`. The fresh output root is
`$HOME/barncompute-m1-c2-2026-10-01`; the owner reported
`MAC C2 DEPENDENCIES READY` after the separate production-PyPI dependency step.
The subsequent owner-shared output established:

- `pip check`: `No broken requirements found.`
- `barn --version`: `0.1.0a1`.
- Separate wheel SHA-256 matches the Windows/published hash above.
- All 30 installed wheel entries excluding `RECORD` match byte-for-byte.
- Import resolves inside the fresh environment.
- Pip installation report contains exactly one installed artifact; its HTTPS
  source is the same `test-files.pythonhosted.org` wheel URL above and its
  recorded SHA-256 matches the separate download.
- Dependency, installation and download logs were retained, with path-redacted
  copies generated by the successful verification checkpoint.
- Disposable HTTPS enrolment and explicit approval passed.
- Heartbeat and registry passed; node and Barn identities were reloaded from
  persistent state and matched. This checks persistence, not a process restart.
- Coordinator listener shutdown passed.

Final smoke output:

```text
UTC: 2026-10-01T02:33:32.882683+00:00
Verified HTTPS enrolment/approval: PASS
Heartbeat and registry: PASS
Persisted identities: PASS
Listener shutdown: PASS
MAC C2 SMOKE PASS
```

Retained Mac evidence under the output root: `install-report.json`, downloaded
wheel, the three `.redacted.log` files, `file-verification.txt` and
`smoke-result.txt`. Disposable private state is under `mac-smoke-state` and must
not be published. The Mac smoke used one logical node and did not rerun a file
transfer. Windows additionally exercised a small local direct transfer.
Fresh Mac pip version, OS build and architecture were not captured in this
checkpoint; historical host details are not presented as new measurements.

## Remaining closure

Collect C3 synchronized observations during overlapping
physical bidirectional transfers. The Mac is available. The owner currently has
no approved relay host/domain/TLS certificate, so C4 and the public portion of C5
cannot yet be run. C5's outbound coordinator control path is still unimplemented.
