"""TLS certificate checks, storage, and self-signed generation."""

from __future__ import annotations

import datetime
import ipaddress
import os
import re
import ssl
import tempfile
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from openrecognition.config import Settings


def _expires(cert: x509.Certificate) -> datetime.datetime:
    expires = getattr(cert, "not_valid_after_utc", None)
    if expires is None:
        expires = cert.not_valid_after.replace(tzinfo=datetime.timezone.utc)
    return expires


def validate_hostname(value: str) -> str:
    text = value.strip().rstrip(".")
    if not text or len(text) > 253:
        raise ValueError("Certificate name is empty or too long")
    try:
        ipaddress.ip_address(text)
        return text
    except ValueError:
        pass
    if not re.fullmatch(r"[A-Za-z0-9.-]+", text) or ".." in text:
        raise ValueError("Certificate name must be a hostname or IP address")
    return text


def load_pair(cert_pem: bytes, key_pem: bytes) -> x509.Certificate:
    if b"BEGIN CERTIFICATE" not in cert_pem or b"PRIVATE KEY" not in key_pem:
        raise ValueError("Certificate and private key must be PEM")
    with tempfile.TemporaryDirectory() as tmp:
        cert_path = Path(tmp) / "cert.pem"
        key_path = Path(tmp) / "key.pem"
        cert_path.write_bytes(cert_pem)
        key_path.write_bytes(key_pem)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)
    return x509.load_pem_x509_certificate(cert_pem)


def certs_readable(cert_file: str, key_file: str) -> bool:
    if not cert_file or not key_file:
        return False
    try:
        load_pair(Path(cert_file).read_bytes(), Path(key_file).read_bytes())
    except (OSError, ValueError):
        return False
    return True


def inspect_files(cert_file: str, key_file: str) -> dict[str, str | bool]:
    if not cert_file and not key_file:
        return {
            "tls_configured": False,
            "tls_readable": False,
            "tls_subject": "",
            "tls_expires_at": "",
            "tls_error": "",
        }
    try:
        cert = load_pair(Path(cert_file).read_bytes(), Path(key_file).read_bytes())
    except (OSError, ValueError) as exc:
        return {
            "tls_configured": True,
            "tls_readable": False,
            "tls_subject": "",
            "tls_expires_at": "",
            "tls_error": str(exc),
        }
    return {
        "tls_configured": True,
        "tls_readable": True,
        "tls_subject": cert.subject.rfc4514_string(),
        "tls_expires_at": _expires(cert).isoformat(),
        "tls_error": "",
    }


def write_pair(settings: Settings, cert_pem: str, key_pem: str) -> tuple[str, str]:
    cert = load_pair(cert_pem.encode(), key_pem.encode())
    del cert
    directory = Path(settings.data_dir) / "tls"
    directory.mkdir(parents=True, exist_ok=True)
    cert_path = directory / "cert.pem"
    key_path = directory / "key.pem"
    cert_text = cert_pem if cert_pem.endswith("\n") else cert_pem + "\n"
    key_text = key_pem if key_pem.endswith("\n") else key_pem + "\n"
    key_path.write_text(key_text)
    os.chmod(key_path, 0o600)
    cert_path.write_text(cert_text)
    return str(cert_path), str(key_path)


def generate_self_signed(hostname: str) -> dict[str, str]:
    name = validate_hostname(hostname)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.datetime.now(datetime.timezone.utc)
    common = name if len(name) <= 64 else "openrecognition"
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common)])
    try:
        alt: x509.GeneralName = x509.IPAddress(ipaddress.ip_address(name))
    except ValueError:
        alt = x509.DNSName(name)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName([alt]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()
    return {
        "cert_pem": cert_pem,
        "key_pem": key_pem,
        "subject": cert.subject.rfc4514_string(),
        "expires_at": _expires(cert).isoformat(),
    }
