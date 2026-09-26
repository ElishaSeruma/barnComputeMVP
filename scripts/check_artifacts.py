"""Screen release archives for local state/secrets and required runtime modules."""

import hashlib
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


def screen(path: Path, names: list[str]) -> None:
    forbidden = {"local-state", "test-state", ".git", ".uv-cache", ".uv-python", "__pycache__"}
    for name in names:
        parts = PurePosixPath(name).parts
        if any(part in forbidden or part.startswith(".venv") for part in parts):
            raise SystemExit(f"Forbidden package entry: {name}")
        suffix = PurePosixPath(name).suffix
        if suffix in {".pem", ".key", ".token", ".db", ".sqlite", ".pyc", ".log"}:
            raise SystemExit(f"Secret/state package entry: {name}")
        if any(part.startswith(".coverage") for part in parts):
            raise SystemExit(f"Coverage package entry: {name}")
    for required in ("relay_transport.py", "node/authority.py", "server.py"):
        if not any(name.endswith("barn_compute/" + required) for name in names):
            raise SystemExit(f"Missing runtime module: {required}")
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    print(f"PASS {path.name} {digest}")


if __name__ == "__main__":
    artifacts = list(Path("dist").glob("*.whl")) + list(Path("dist").glob("*.tar.gz"))
    if not artifacts:
        raise SystemExit("No release artifacts found")
    for artifact in artifacts:
        if artifact.suffix == ".whl":
            with zipfile.ZipFile(artifact) as archive:
                screen(artifact, archive.namelist())
        else:
            with tarfile.open(artifact) as archive:
                screen(artifact, archive.getnames())
