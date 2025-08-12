"""Servidor proxy HTTP/HTTPS.

O encaminhamento é feito na mão sobre o http.server da biblioteca padrão:
  - Requisições HTTP comuns chegam em absolute-form (http://host/caminho).
  - HTTPS chega como CONNECT host:porta; respondemos 200, terminamos o TLS
    do cliente com um certificado emitido pela nossa CA e então lemos as
    requisições já decifradas.

Cada requisição passa pelo interceptor (que pode pausá-la), é encaminhada
ao servidor de destino e o par requisição/resposta vira um flow no histórico.
"""

from __future__ import annotations

import http.client
import ssl
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, urlunsplit

from .ca import CertificateAuthority
from .flow import Flow, Request, Response
from .http_parser import split_authority, strip_hop_by_hop
from .interceptor import Interceptor
from .storage import FlowStore

# Contexto TLS para falar com o destino. A verificação de certificado do
# servidor fica desligada de propósito, para permitir inspecionar qualquer
# alvo autorizado sem esbarrar em cadeias desconhecidas.
_UPSTREAM_TLS = ssl.create_default_context()
_UPSTREAM_TLS.check_hostname = False
_UPSTREAM_TLS.verify_mode = ssl.CERT_NONE


class ProxyServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, store: FlowStore, interceptor: Interceptor, ca: CertificateAuthority):
        super().__init__(address, ProxyHandler)
        self.store = store
        self.interceptor = interceptor
        self.ca = ca
        self.upstream_timeout = 30


class ProxyHandler(BaseHTTPRequestHandler):
    # Mantém keep-alive com o cliente; sempre enviamos Content-Length.
    protocol_version = "HTTP/1.1"

    # Marcados em do_CONNECT quando a conexão é HTTPS interceptada.
    _tls = False
    _tls_host = ""
    _tls_port = 443

    # Silencia o log padrão do http.server; o histórico é a nossa visão.
    def log_message(self, *args) -> None:  # noqa: D401
        return

    # ------------------------------------------------------------------
    # Verbos HTTP: todos caem no mesmo tratamento.
    # ------------------------------------------------------------------
    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def do_PUT(self):
        self._handle()

    def do_DELETE(self):
        self._handle()

    def do_HEAD(self):
        self._handle()

    def do_OPTIONS(self):
        self._handle()

    def do_PATCH(self):
        self._handle()

    # ------------------------------------------------------------------
    # CONNECT: abre o túnel e passa a interceptar o TLS.
    # ------------------------------------------------------------------
    def do_CONNECT(self):
        host, port = split_authority(self.path, 443)
        try:
            self.send_response_only(200, "Connection Established")
            self.end_headers()
            self.wfile.flush()
        except OSError:
            return

        try:
            context = self.server.ca.server_context(host)
            tls_sock = context.wrap_socket(self.connection, server_side=True)
        except (ssl.SSLError, OSError):
            # Cliente desistiu do handshake ou não confia na CA.
            return

        # A partir daqui, lemos e escrevemos no socket já decifrado.
        self.connection = tls_sock
        self.rfile = tls_sock.makefile("rb")
        self.wfile = tls_sock.makefile("wb")
        self._tls = True
        self._tls_host = host
        self._tls_port = port

        # Atende requisições sucessivas sobre o mesmo túnel.
        self.close_connection = False
        while not self.close_connection:
            self.handle_one_request()

    # ------------------------------------------------------------------
    # Tratamento comum de requisição.
    # ------------------------------------------------------------------
    def _handle(self):
        try:
            request = self._build_request()
        except Exception:
            self.close_connection = True
            return

        flow = Flow(id=self.server.store.next_id(), request=request)

        # Ponto de interceptação: pode pausar, editar ou descartar.
        forwarded = self.server.interceptor.handle(flow)
        if forwarded is None:
            flow.error = "descartada na interceptação"
            self.server.store.add(flow)
            self._send_simple(502, "Request dropped by byproxy")
            return
        flow.request = forwarded

        started = time.time()
        try:
            response = self._forward(forwarded)
        except Exception as exc:  # falha ao falar com o destino
            flow.error = str(exc)
            flow.duration_ms = (time.time() - started) * 1000
            self.server.store.add(flow)
            self._send_simple(502, f"byproxy upstream error: {exc}")
            return

        flow.response = response
        flow.duration_ms = (time.time() - started) * 1000
        self.server.store.add(flow)
        self._relay_response(response)

    def _build_request(self) -> Request:
        if self._tls:
            scheme = "https"
            host = self._tls_host
            port = self._tls_port
            path = self.path  # já vem em origin-form
        else:
            parsed = urlsplit(self.path)
            scheme = parsed.scheme or "http"
            host = parsed.hostname or ""
            port = parsed.port or (443 if scheme == "https" else 80)
            path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))

        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b""

        return Request(
            method=self.command,
            scheme=scheme,
            host=host,
            port=port,
            path=path,
            http_version=self.request_version,
            headers=list(self.headers.items()),
            body=body,
        )

    def _forward(self, req: Request) -> Response:
        if req.scheme == "https":
            conn = http.client.HTTPSConnection(
                req.host, req.port, timeout=self.server.upstream_timeout, context=_UPSTREAM_TLS
            )
        else:
            conn = http.client.HTTPConnection(
                req.host, req.port, timeout=self.server.upstream_timeout
            )

        headers = dict(strip_hop_by_hop(req.headers))
        try:
            conn.request(req.method, req.path, body=req.body or None, headers=headers)
            raw = conn.getresponse()
            body = raw.read()
            return Response(
                status_code=raw.status,
                reason=raw.reason or "",
                http_version="HTTP/1.1",
                headers=list(raw.getheaders()),
                body=body,
            )
        finally:
            conn.close()

    def _relay_response(self, response: Response) -> None:
        try:
            self.send_response_only(response.status_code, response.reason)
            # Reescrevemos o Content-Length porque já temos o corpo inteiro,
            # e removemos cabeçalhos ponto-a-ponto (incl. transfer-encoding).
            for key, value in strip_hop_by_hop(response.headers):
                if key.lower() == "content-length":
                    continue
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(response.body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(response.body)
            self.wfile.flush()
        except OSError:
            self.close_connection = True

    def _send_simple(self, status: int, message: str) -> None:
        payload = message.encode("utf-8")
        try:
            self.send_response_only(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            self.wfile.flush()
        except OSError:
            self.close_connection = True
