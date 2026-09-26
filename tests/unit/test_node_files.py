from pathlib import Path

import pytest

from barn_compute.errors import BarnError, ErrorCode
from barn_compute.models import CHUNK_SIZE
from barn_compute.node.service import NodeService


def initialized_node(tmp_path: Path) -> NodeService:
    node = NodeService(tmp_path / "node")
    node.initialize("NodeA", "127.0.0.2")
    return node


def test_import_file_creates_immutable_manifest_and_copy(tmp_path: Path) -> None:
    node = initialized_node(tmp_path)
    source = tmp_path / "payload.bin"
    source.write_bytes(b"a" * CHUNK_SIZE + b"b")

    manifest = node.import_file(source)

    assert manifest.display_name == "payload.bin"
    assert manifest.size == CHUNK_SIZE + 1
    assert [chunk.length for chunk in manifest.chunks] == [CHUNK_SIZE, 1]
    stored = node.state_dir / "managed" / str(manifest.file_id)
    assert (stored / "data").read_bytes() == source.read_bytes()
    assert node.list_files() == [manifest]


def test_zero_byte_file_is_supported(tmp_path: Path) -> None:
    node = initialized_node(tmp_path)
    source = tmp_path / "empty.bin"
    source.write_bytes(b"")

    manifest = node.import_file(source)

    assert manifest.size == 0
    assert manifest.chunks == ()
    assert (node.state_dir / "managed" / str(manifest.file_id) / "data").read_bytes() == b""


def test_oversized_file_is_rejected(tmp_path: Path) -> None:
    node = initialized_node(tmp_path)
    source = tmp_path / "large.bin"
    with source.open("wb") as handle:
        handle.seek(512 * 1024 * 1024)
        handle.write(b"x")

    with pytest.raises(BarnError) as error:
        node.import_file(source)
    assert error.value.code is ErrorCode.INVALID_REQUEST
