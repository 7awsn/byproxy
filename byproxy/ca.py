"""Autoridade certificadora local para interceptação de HTTPS.

Para inspecionar HTTPS o proxy precisa terminar a conexão TLS do cliente.
Isso só funciona se o cliente confiar em um certificado emitido por nós.
Este módulo cria uma CA própria (uma vez) e, sob demanda, emite um
certificado para cada domínio acessado, assinado por essa CA.

Use isto apenas em dispositivos e ambientes que você tem autorização
para testar.
"""

from __future__ import annotations

import datetime
import ipaddress
import ssl
import threading
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def default_ca_dir() -> Path:
    # Guarda a CA no diretório home do usuário para reaproveitar entre execuções.
    return Path.home() / ".byproxy"


class CertificateAuthority:
    def __init__(self, ca_dir: Path | None = None):
        self.ca_dir = ca_dir or default_ca_dir()
        self.certs_dir = self.ca_dir / "certs"
        self.ca_cert_path = self.ca_dir / "byproxy-ca.pem"
        self.ca_key_path = self.ca_dir / "byproxy-ca.key"

        self.ca_dir.mkdir(parents=True, exist_ok=True)
        self.certs_dir.mkdir(parents=True, exist_ok=True)

        # Cache de contextos TLS por domínio, para não reemitir toda vez.
        self._contexts: dict[str, ssl.SSLContext] = {}
        self._lock = threading.Lock()

        self._ca_cert: x509.Certificate
        self._ca_key: rsa.RSAPrivateKey
        self._load_or_create_ca()

    # ------------------------------------------------------------------
    # CA raiz
    # ------------------------------------------------------------------
    def _load_or_create_ca(self) -> None:
        if self.ca_cert_path.exists() and self.ca_key_path.exists():
            self._ca_cert = x509.load_pem_x509_certificate(self.ca_cert_path.read_bytes())
            self._ca_key = serialization.load_pem_private_key(
                self.ca_key_path.read_bytes(), password=None
            )
            return
        self._create_ca()

    def _create_ca(self) -> None:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "byproxy CA"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "byproxy"),
        ])
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_cert_sign=True,
                    crl_sign=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(key, hashes.SHA256())
        )

        self.ca_key_path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )
        self.ca_cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        self._ca_cert = cert
        self._ca_key = key

    # ------------------------------------------------------------------
    # Certificados por domínio
    # ------------------------------------------------------------------
    def server_context(self, host: str) -> ssl.SSLContext:
        """Devolve um contexto TLS de servidor para o domínio informado."""
        with self._lock:
            if host in self._contexts:
                return self._contexts[host]
            cert_path = self._ensure_leaf_cert(host)
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(certfile=str(cert_path))
            self._contexts[host] = ctx
            return ctx

    def _ensure_leaf_cert(self, host: str) -> Path:
        safe = host.replace(":", "_").replace("*", "_")
        cert_path = self.certs_dir / f"{safe}.pem"
        if cert_path.exists():
            return cert_path

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
        now = datetime.datetime.now(datetime.timezone.utc)

        # O SAN aceita tanto nome de domínio quanto IP literal.
        try:
            san = x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(host))])
        except ValueError:
            san = x509.SubjectAlternativeName([x509.DNSName(host)])

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(self._ca_cert.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=825))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(san, critical=False)
            .add_extension(
                x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
                critical=False,
            )
            .sign(self._ca_key, hashes.SHA256())
        )

        # Grava cert e chave no mesmo arquivo PEM (formato aceito por load_cert_chain).
        pem = cert.public_bytes(serialization.Encoding.PEM)
        pem += key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
        cert_path.write_bytes(pem)
        return cert_path
