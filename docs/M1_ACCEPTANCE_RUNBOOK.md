# M1 completion and Mac acceptance runbook

M1 is accepted only after automated tests, released-package installation, and
physical Windows/macOS direct and public-relay tests pass. Local WSS tests use
real TLS sockets, but do not prove that public Wi-Fi permits the deployed relay.
Record PASS, FAIL, or NOT RUN for every gate. Retain previous failure reports.

## Mac setup and automated testing

Use the local Developer checkout, outside iCloud Desktop/Documents. Python
3.11 or 3.12 is required. The new runtime dependency is `websockets>=15,<16`;
refresh the environment before testing. No public relay, administrator rights,
firewall changes, or credentials are needed for the automated suite.

```sh
cd /Users/elisha/Developer/barnComputeMVP
git pull --ff-only origin main
python3.12 -m venv .venv-m1
./.venv-m1/bin/python -m pip install --upgrade pip
./.venv-m1/bin/python -m pip install -e '.[dev]'
./.venv-m1/bin/python -m ruff check .
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  ./.venv-m1/bin/python -m pytest -p pytest_cov -q \
  --cov=barn_compute --cov-report=term-missing --junitxml=local-state/mac-m1-tests.xml
./.venv-m1/bin/python -m build
./.venv-m1/bin/python -m twine check dist/*
./.venv-m1/bin/python scripts/check_artifacts.py
```

Allow several minutes for the network suite. It starts disposable loopback
HTTPS/WSS services on dynamically allocated ports and stops them at teardown.
It writes deterministic 100 MiB files without allocating each file in memory.
The suite exercises signed remote shares, real direct HTTPS, recipient proof,
nonce replay rejection, live revocation, real encrypted WSS transfers in both
directions, journal reuse after grant renewal, and automatic relay fallback
when the direct port is unavailable. It also checks chunk-boundary files,
corrupt journals, cancellation/resume, no-clobber publication, and unknown CAs.

To isolate the new network acceptance tests:

```sh
./.venv-m1/bin/python -m pytest tests/integration/test_m1_network.py -q
```

Record commit SHA, macOS/Python versions, exact commands, count, coverage,
duration, warnings, build/Twine outcomes, and any failure traceback in a new
dated file under `docs/mac_test_results`. Coverage may differ by platform;
matching pass/fail behavior and the same committed code are required.

## Physical two-machine setup

The Mac hosts the coordinator plus its own node; Windows runs a separate node.
Select stable LAN IPs or DNS names before initializing certificates. Certificate
SANs must match the URLs used. Use separate private state directories for the
coordinator and each node. Back up private state; never copy identity keys to
the other machine or the relay.

On the Mac, in an activated environment:

```sh
barn coordinator init --name LabBarn --advertise <MAC_IP> --state-dir <COORD_STATE>
barn coordinator ca export --output ./barn-ca.pem --state-dir <COORD_STATE>
barn coordinator grant-key-export --output ./grant-public.key --state-dir <COORD_STATE>
barn coordinator start --bind 0.0.0.0 --port 8443 --state-dir <COORD_STATE>
```

Leave the service running and use another terminal for administration. Convey
the public CA and independently verified fingerprint to both nodes. The grant
public key goes to the relay. Only these public files need to leave the Mac.

For each node, create a separate one-use invite on the Mac:

```sh
barn coordinator invite --ttl 10m --state-dir <COORD_STATE>
```

Then on the corresponding node host:

```sh
barn node init --name <NODE_NAME> --advertise <NODE_IP> --peer-port 8445 --state-dir <NODE_STATE>
barn node enroll --coordinator https://<MAC_IP>:8443 --ca-cert ./barn-ca.pem --ca-fingerprint <FINGERPRINT> --state-dir <NODE_STATE>
```

Enter the invitation at the private prompt. On the Mac, list and approve the
request after checking the displayed identity fingerprint:

```sh
barn coordinator enrolments --state-dir <COORD_STATE>
barn coordinator approve <REQUEST_ID> --state-dir <COORD_STATE>
```

On the node host:

```sh
barn node enrolment-status --coordinator https://<MAC_IP>:8443 --ca-cert ./barn-ca.pem --state-dir <NODE_STATE>
barn node start --coordinator https://<MAC_IP>:8443 --bind 0.0.0.0 --state-dir <NODE_STATE>
```

Allow the Python service's specific incoming LAN connections through the host
firewall where needed. The coordinator admin port 8754 and node local port 8755
stay bound to loopback. Remote nodes authenticate with their own identity;
they never need the coordinator's admin token. The node agent sends heartbeat
and refreshes registry every 15 seconds, retrying coordinator failures.

## Direct transfer and recovery

On the source, import a deterministic 100 MiB file and create a share:

```sh
python scripts/make_m1_fixture.py ./m1-100m.bin
barn file add <FIXTURE> --state-dir <SOURCE_STATE>
barn share create <FILE_ID> --to <RECIPIENT_NODE_ID> --ttl 1h --coordinator https://<MAC_IP>:8443 --state-dir <SOURCE_STATE>
```

On the recipient:

```sh
barn share inbox --coordinator https://<MAC_IP>:8443 --state-dir <RECIPIENT_STATE>
barn share fetch <SHARE_ID> --coordinator https://<MAC_IP>:8443 --source https://<SOURCE_IP>:8445 --ca-cert ./barn-ca.pem --mode direct --output <NEW_DESTINATION> --state-dir <RECIPIENT_STATE>
barn transfer list --state-dir <RECIPIENT_STATE>
```

Compare SHA-256 at both ends (`shasum -a 256` on Mac, `Get-FileHash -Algorithm
SHA256` in PowerShell). Repeat in the opposite direction. Test 0-byte, 1-byte,
1 MiB, and 1 MiB + 1 byte files. Existing destinations must remain untouched.

Interrupt an active fetch with Ctrl+C, record completed chunk indexes using
`barn transfer status <TRANSFER_ID>`, restart the node and coordinator, and
fetch the same share to a new destination. A renewed grant retains the share's
transfer ID; the receiver validates persisted chunks before skipping them.
To cancel explicitly, use `barn transfer cancel <TRANSFER_ID>`. To re-enable
the journal, run `barn transfer resume <TRANSFER_ID>` and fetch the same share.
Corrupt an isolated test chunk and verify that it is downloaded again.

Revoke a source-owned share with `barn share revoke <SHARE_ID> --coordinator
https://<MAC_IP>:8443 --state-dir <SOURCE_STATE>` and verify delivery is denied.
Revoke a disposable node from the coordinator host with `barn node revoke
<NODE_ID> --state-dir <COORD_STATE>`; grants, identities, heartbeats, and delivery
must then be denied. Revocation is irreversible for that enrollment; use new
disposable state for further tests.

## Public relay setup needed from the owner

Provide a reachable server and DNS name, with outbound connectivity from both
computers to TCP 443, and a valid TLS certificate/key for that relay domain.
Install the same package and its dependencies there. Install only the public
coordinator grant key, plus the relay's own TLS certificate and private key.
Never install the Barn CA private key, node private identities, coordinator
state, or admin tokens on the relay.

```sh
barn relay serve --grant-public-key /private/relay/grant-public.key --cert /private/relay/fullchain.pem --key /private/relay/privkey.pem --bind 0.0.0.0 --port 443
```

Keep this process running under the host's normal service manager. Ensure the
TLS key is readable only by the service account. If using a reverse proxy,
forward `/v1/tunnel` as a WebSocket with a 2 MiB maximum message and bounded
timeouts. The relay supports one configured Barn grant key per process.

Restart both agents with the same explicitly chosen relay:

```sh
barn node start --coordinator https://<MAC_IP>:8443 --relay-url wss://<RELAY_DOMAIN>/v1/tunnel --state-dir <NODE_STATE>
```

For a private test relay CA, also supply `--relay-ca-cert <RELAY_CA_PEM>` to
each agent and fetch. For a public trusted certificate, omit this option.
Never disable certificate verification.

```sh
barn share fetch <SHARE_ID> --coordinator https://<MAC_IP>:8443 --source https://<SOURCE_IP>:8445 --ca-cert ./barn-ca.pem --mode relay --relay-url wss://<RELAY_DOMAIN>/v1/tunnel --output <NEW_DESTINATION> --state-dir <RECIPIENT_STATE>
```

Both nodes still require HTTPS access to the coordinator. The relay only
transports file data; it does not proxy the coordinator. If the coordinator
cannot be reached on public Wi-Fi, make its verified HTTPS service reachable
through an explicitly managed network route before this test.

Block only inbound peer traffic while preserving coordinator and relay access;
repeat with `--mode auto` and verify `Transport: relay` and matching SHA-256.
Interrupt a direct transfer, block its peer path, and fetch the same share
through relay; verify already committed chunks are reused. Stop the relay and
verify forced relay mode fails cleanly; restart it and repeat the fetch.
Measure process memory and elapsed time while both 100 MiB directions run.
Relay sessions expire after five minutes and are bounded to eight simultaneous
source workers, 64 admitted relay sockets, 1 MiB frames, 2 MiB logical packets,
and 768 MiB forwarded bytes per socket. Fetch again to renew expired authority
and resume the journal. Record expiry and outage behavior explicitly.

## TestPyPI release and clean installation

The owner must supply a TestPyPI account, package-name availability, and a
securely configured upload token or trusted publisher. No credentials have
been configured or publication performed by this checkpoint. Confirm artifacts
contain only package/documentation sources, with no local state or secrets.

Upload the inspected wheel/sdist with `python -m twine upload --repository
testpypi dist/*`, using a private credential prompt or a secure credential
store. Never pass tokens in commands or record them in this repository.

In a clean Python 3.11/3.12 environment on EACH physical machine, install the
runtime dependencies from production PyPI first, then the package from TestPyPI:

```sh
python -m pip install 'cryptography>=44,<46' 'fastapi>=0.116,<1' 'httpx>=0.28,<1' 'platformdirs>=4.3,<5' 'pydantic>=2.10,<3' 'typer>=0.15,<1' 'uvicorn>=0.35,<1' 'websockets>=15,<16'
python -m pip install --index-url https://test.pypi.org/simple/ --no-deps barnCompute==0.1.0a1
barn --version
```

Use PowerShell-compatible quoting on Windows. Record the actual download URLs,
version, artifact SHA-256, and physical test results for both installations.
Local editable or wheel installs validate development but do not satisfy this
release-provenance gate.

## Final evidence checklist

The coordinator's last 100 administrative events can be inspected with
`barn coordinator audit --state-dir <COORD_STATE>`. These entries contain
operations and UUIDs, without tokens, invitations, private keys or file bytes.

| Gate | Required evidence |
| --- | --- |
| Windows automation | Ruff, full suite, real TLS/WSS and failover tests |
| Mac automation | Same commit and passing suite; build, Twine, clean wheel |
| Package provenance | Same TestPyPI release installed on both hosts |
| Physical LAN | 100 MiB both directions, hashes, boundary files |
| Recovery | Restart, cancellation, missing/corrupt chunk repair, reused chunks |
| Security | Revoked/expired/wrong-recipient/replayed access denied |
| Public relay | Forced relay, blocked direct fallback, outage/recovery, TLS |
| Resources | Memory, disk, concurrency and elapsed-time observations |

Only after these gates pass should `docs/test-report.md` change its release
verdict to M1 ACCEPTED. Automated local results do not replace the physical or
release-provenance evidence.
