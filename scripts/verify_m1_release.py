"""Collect C2 evidence in a fresh environment without touching existing Barn state."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
import venv
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

VERSION = "0.1.0a1"
WHEEL_SHA256 = "f1cbc28f916749b15cc46a2e5ab7760ad27d9693153c76e36ec2d070f85acd86"
DEPENDENCIES = [
    "cryptography>=44.0,<46", "fastapi>=0.116,<1", "httpx>=0.28,<1",
    "platformdirs>=4.3,<5", "pydantic>=2.10,<3", "typer>=0.15,<1",
    "uvicorn>=0.35,<1", "websockets>=15,<16",
]


def clean_environment() -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items()
        if not key.upper().startswith(("PIP_", "PYTHON"))
    }
    environment.update(
        PIP_CONFIG_FILE=os.devnull,
        PIP_DISABLE_PIP_VERSION_CHECK="1",
        PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1",
    )
    return environment


def redact_log(root: Path, name: str) -> None:
    public_log = (root / f"{name}.log").read_text(encoding="utf-8", errors="replace")
    for private_path, replacement in ((root, "<C2_OUTPUT>"), (Path.home(), "<HOME>")):
        for spelling in (str(private_path), private_path.as_posix()):
            public_log = re.sub(re.escape(spelling), replacement, public_log, flags=re.IGNORECASE)
    (root / f"{name}.redacted.log").write_text(public_log, encoding="utf-8")


def run(command: list[str], root: Path, name: str, timeout: int = 600) -> None:
    print(f"Running {name}", flush=True)
    with (root / f"{name}.log").open("x", encoding="utf-8") as log:
        result = subprocess.run(
            command, cwd=root, env=clean_environment(), stdout=log,
            stderr=subprocess.STDOUT, timeout=timeout, check=False,
        )
    redact_log(root, name)
    if result.returncode:
        raise RuntimeError(f"{name} failed; inspect its local log")


def smoke(root: Path) -> None:
    # Imported only by the freshly installed interpreter, never the development env.
    import socket
    import threading
    from contextlib import ExitStack, contextmanager

    import uvicorn

    from barn_compute.coordinator.app import create_public_app
    from barn_compute.coordinator.service import CoordinatorService
    from barn_compute.node.app import create_peer_app
    from barn_compute.node.authority import PeerAuthority
    from barn_compute.node.client import CoordinatorClient, PeerClient
    from barn_compute.node.service import NodeService

    @contextmanager
    def listener(app, certificate, key):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(
            app, ssl_certfile=str(certificate), ssl_keyfile=str(key),
            access_log=False, log_level="error", lifespan="off",
        ))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 15
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Smoke listener did not start")
                time.sleep(0.05)
            yield f"https://127.0.0.1:{port}"
        finally:
            server.should_exit = True
            thread.join(15)
            sock.close()
            if thread.is_alive():
                raise RuntimeError("Smoke listener did not stop")

    coordinator = CoordinatorService(root / "private-smoke-state" / "coordinator")
    metadata = coordinator.initialize("C2Smoke", "127.0.0.1")
    with ExitStack() as stack:
        url = stack.enter_context(listener(
            create_public_app(coordinator), coordinator.state_dir / "coordinator-cert.pem",
            coordinator.state_dir / "secrets" / "coordinator-key.pem",
        ))
        nodes, clients, peers = [], [], []
        for index in range(2):
            node = NodeService(root / "private-smoke-state" / f"node-{index}")
            node.initialize(f"C2Node{index}", "127.0.0.1")
            ca = coordinator.state_dir / "ca-cert.pem"
            node.pin_barn_ca(ca.read_bytes(), metadata.ca_fingerprint)
            client = stack.enter_context(CoordinatorClient(url, ca))
            invite = coordinator.create_invite(timedelta(minutes=5))
            receipt = client.submit_enrolment(node, invite.code)
            coordinator.approve_enrolment(str(receipt.request_id))
            client.poll_enrolment(node)
            if client.send_heartbeat(node)["status"] != "ONLINE":
                raise RuntimeError("Heartbeat failed")
            nodes.append(node)
            clients.append(client)
            peers.append(stack.enter_context(listener(
                create_peer_app(node, PeerAuthority(node, client)),
                node.state_dir / "node-cert.pem", node.state_dir / "secrets" / "tls-key.pem",
            )))
        if len(clients[0].refresh_registry(nodes[0])["nodes"]) != 2:
            raise RuntimeError("Registry did not contain both nodes")
        source = root / "smoke-input.bin"
        source.write_bytes(b"barnCompute C2 release provenance smoke\n")
        manifest = nodes[0].import_file(source)
        share = clients[0].signed(nodes[0], "POST", "/v1/shares", {
            "file_id": str(manifest.file_id),
            "source_node_id": str(nodes[0].load_metadata().node_id),
            "recipient_node_id": str(nodes[1].load_metadata().node_id),
            "ttl_seconds": 300,
        })
        grant = clients[1].signed(nodes[1], "POST", f"/v1/shares/{share['share_id']}/grant")
        with PeerClient(peers[0], nodes[1].state_dir / "barn-ca.pem") as peer:
            destination = peer.download(nodes[1], grant, root / "smoke-output.bin")
        if destination.read_bytes() != source.read_bytes():
            raise RuntimeError("Smoke transfer content mismatch")


def verify(root: Path) -> None:
    import importlib.metadata

    import barn_compute

    wheel, = (root / "download").glob("*.whl")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    if digest != WHEEL_SHA256:
        raise RuntimeError("Downloaded wheel differs from recorded published M1 artifact")
    distribution = importlib.metadata.distribution("barnCompute")
    if distribution.version != VERSION:
        raise RuntimeError("Installed version differs")
    origin = Path(barn_compute.__file__).resolve()
    if not origin.is_relative_to((root / "venv").resolve()):
        raise RuntimeError("Package import did not resolve inside the fresh environment")
    checked = 0
    with zipfile.ZipFile(wheel) as archive:
        for member in archive.infolist():
            if member.is_dir() or member.filename.endswith(".dist-info/RECORD"):
                continue
            installed = Path(distribution.locate_file(member.filename))
            if installed.read_bytes() != archive.read(member):
                raise RuntimeError(f"Installed file differs: {member.filename}")
            checked += 1
    report = json.loads((root / "install-report.json").read_text(encoding="utf-8"))
    if len(report["install"]) != 1:
        raise RuntimeError("TestPyPI step installed more than the requested package")
    artifact = report["install"][0]["download_info"]
    if artifact["archive_info"]["hashes"]["sha256"] != digest:
        raise RuntimeError("Installer artifact hash differs from separately downloaded wheel")
    from urllib.parse import urlsplit

    url = urlsplit(artifact["url"])
    if url.scheme != "https" or url.hostname != "test-files.pythonhosted.org":
        raise RuntimeError("Installer source was not the TestPyPI file service")
    smoke(root)
    result = {
        "status": "PASS", "utc": datetime.now(UTC).isoformat(),
        "platform": platform.platform(), "architecture": platform.machine(),
        "python": platform.python_version(), "pip": importlib.metadata.version("pip"),
        "version": distribution.version, "wheel": wheel.name,
        "wheel_sha256": digest, "installer_url": artifact["url"],
        "matched_wheel_entries_excluding_record": checked,
        "import_origin": "venv site-packages/barn_compute",
        "smoke": "HTTPS enrolment/approval, heartbeat/registry, direct small-file transfer",
        "scope": "One physical host; disposable local logical nodes, not cross-host acceptance",
    }
    (root / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--verify", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.output.expanduser().resolve()
    if args.verify:
        verify(root)
        return
    if sys.version_info[:2] not in ((3, 11), (3, 12)):
        raise SystemExit("Use Python 3.11 or 3.12")
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    print(f"Creating fresh environment in {root}", flush=True)
    venv.EnvBuilder(with_pip=True).create(root / "venv")
    python = root / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    barn = root / "venv" / ("Scripts/barn.exe" if os.name == "nt" else "bin/barn")
    pip = [str(python), "-m", "pip", "--no-input", "--no-cache-dir"]
    run([*pip, "install", "--index-url", "https://pypi.org/simple/", *DEPENDENCIES],
        root, "dependencies")
    run([*pip, "install", "-v", "--index-url", "https://test.pypi.org/simple/",
         "--no-deps", "--report", str(root / "install-report.json"), f"barnCompute=={VERSION}"],
        root, "testpypi-install")
    run([*pip, "download", "--index-url", "https://test.pypi.org/simple/", "--no-deps",
         "--only-binary=:all:", "--dest", str(root / "download"), f"barnCompute=={VERSION}"],
        root, "testpypi-download")
    run([*pip, "check"], root, "pip-check")
    run([str(barn), "--version"], root, "barn-version")
    run([str(python), str(Path(__file__).resolve()), "--output", str(root), "--verify"],
        root, "verification")
    print((root / "result.json").read_text(encoding="utf-8"))
    print("Keep private-smoke-state private; share only reviewed public evidence logs.")


if __name__ == "__main__":
    main()
