"""Key serialization helpers for durable node identities."""

from __future__ import annotations

import os
import stat
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from .config import ensure_private_directory, write_private_bytes


def generate_identity() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def save_private_identity(key: Ed25519PrivateKey, path: Path) -> None:
    ensure_private_directory(path.parent)
    data = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    if os.name != "nt":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def load_private_identity(path: Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("Identity file does not contain an Ed25519 private key")
    return key


def public_key_fingerprint(key: Ed25519PublicKey) -> str:
    import hashlib

    raw = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()


def certificate_fingerprint(certificate: x509.Certificate) -> str:
    from cryptography.hazmat.primitives import hashes

    return certificate.fingerprint(hashes.SHA256()).hex()


def save_certificate(certificate: x509.Certificate, path: Path) -> None:
    write_private_bytes(path, certificate.public_bytes(serialization.Encoding.PEM))


def load_certificate(path: Path) -> x509.Certificate:
    return x509.load_pem_x509_certificate(path.read_bytes())


def create_barn_ca(barn_id: str, name: str) -> tuple[Ed25519PrivateKey, x509.Certificate]:
    key = generate_identity()
    now = datetime.now(UTC)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "barnCompute"),
            x509.NameAttribute(NameOID.COMMON_NAME, f"{name} Barn CA"),
        ]
    )
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.UnrecognizedExtension(
                x509.ObjectIdentifier("1.3.6.1.4.1.62187.1.1"), barn_id.encode()
            ),
            critical=False,
        )
        .sign(key, algorithm=None)
    )
    return key, certificate


def _subject_alternative_name(advertised_host: str) -> x509.SubjectAlternativeName:
    try:
        value: x509.GeneralName = x509.IPAddress(ip_address(advertised_host))
    except ValueError:
        value = x509.DNSName(advertised_host)
    return x509.SubjectAlternativeName([value])


def create_server_certificate(
    ca_key: Ed25519PrivateKey,
    ca_certificate: x509.Certificate,
    common_name: str,
    advertised_host: str,
    *,
    validity: timedelta = timedelta(days=90),
) -> tuple[Ed25519PrivateKey, x509.Certificate]:
    key = generate_identity()
    now = datetime.now(UTC)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "barnCompute"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_certificate.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + validity)
        .add_extension(_subject_alternative_name(advertised_host), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False
        )
        .sign(ca_key, algorithm=None)
    )
    return key, certificate
