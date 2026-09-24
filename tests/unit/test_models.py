from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from barn_compute.models import CHUNK_SIZE, ChunkManifest, FileManifest


def test_zero_byte_manifest_is_valid() -> None:
    manifest = FileManifest(
        file_id=uuid4(),
        owner_node_id=uuid4(),
        display_name="empty.bin",
        size=0,
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        chunks=(),
        created_at=datetime.now(UTC),
    )
    assert manifest.chunks == ()


def test_non_contiguous_chunks_are_rejected() -> None:
    with pytest.raises(ValidationError):
        FileManifest(
            file_id=uuid4(),
            owner_node_id=uuid4(),
            display_name="bad.bin",
            size=1,
            sha256="0" * 64,
            chunks=(
                ChunkManifest(index=1, offset=CHUNK_SIZE, length=1, sha256="0" * 64),
            ),
            created_at=datetime.now(UTC),
        )

