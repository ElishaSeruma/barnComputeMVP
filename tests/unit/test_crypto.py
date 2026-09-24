import pytest

from barn_compute.crypto import (
    generate_identity,
    load_private_identity,
    public_key_fingerprint,
    save_private_identity,
)


def test_identity_round_trip_and_exclusive_creation(tmp_path) -> None:
    path = tmp_path / "private" / "identity.pem"
    key = generate_identity()
    save_private_identity(key, path)
    loaded = load_private_identity(path)
    assert public_key_fingerprint(loaded.public_key()) == public_key_fingerprint(key.public_key())
    with pytest.raises(FileExistsError):
        save_private_identity(generate_identity(), path)

