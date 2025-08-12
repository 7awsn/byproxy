"""Modelo de dados do tráfego capturado.

Um "flow" representa um par requisição/resposta que passou pelo proxy.
Tudo aqui foi pensado para ser facilmente serializável em JSON, para
salvar e recarregar sessões.
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass, field


# Cabeçalhos ponto-a-ponto: valem só para a conexão atual e não devem
# ser repassados adiante pelo proxy.
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "proxy-connection",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


@dataclass
class Request:
    method: str
    scheme: str
    host: str
    port: int
    path: str  # caminho + query (origin-form), ex.: "/busca?q=1"
    http_version: str = "HTTP/1.1"
    headers: list[tuple[str, str]] = field(default_factory=list)
    body: bytes = b""

    @property
    def url(self) -> str:
        # Esconde a porta quando ela é a padrão do esquema.
        default = 443 if self.scheme == "https" else 80
        if self.port == default:
            return f"{self.scheme}://{self.host}{self.path}"
        return f"{self.scheme}://{self.host}:{self.port}{self.path}"

    def header(self, name: str) -> str | None:
        # Busca sem diferenciar maiúsculas de minúsculas.
        name = name.lower()
        for key, value in self.headers:
            if key.lower() == name:
                return value
        return None

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "scheme": self.scheme,
            "host": self.host,
            "port": self.port,
            "path": self.path,
            "http_version": self.http_version,
            "headers": self.headers,
            "body": base64.b64encode(self.body).decode("ascii"),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Request":
        return cls(
            method=data["method"],
            scheme=data["scheme"],
            host=data["host"],
            port=data["port"],
            path=data["path"],
            http_version=data.get("http_version", "HTTP/1.1"),
            headers=[tuple(h) for h in data.get("headers", [])],
            body=base64.b64decode(data.get("body", "")),
        )


@dataclass
class Response:
    status_code: int
    reason: str
    http_version: str = "HTTP/1.1"
    headers: list[tuple[str, str]] = field(default_factory=list)
    body: bytes = b""

    def to_dict(self) -> dict:
        return {
            "status_code": self.status_code,
            "reason": self.reason,
            "http_version": self.http_version,
            "headers": self.headers,
            "body": base64.b64encode(self.body).decode("ascii"),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Response":
        return cls(
            status_code=data["status_code"],
            reason=data.get("reason", ""),
            http_version=data.get("http_version", "HTTP/1.1"),
            headers=[tuple(h) for h in data.get("headers", [])],
            body=base64.b64decode(data.get("body", "")),
        )


@dataclass
class Flow:
    id: int
    request: Request
    response: Response | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    duration_ms: float | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "request": self.request.to_dict(),
            "response": self.response.to_dict() if self.response else None,
            "error": self.error,
            "created_at": self.created_at,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Flow":
        resp = data.get("response")
        return cls(
            id=data["id"],
            request=Request.from_dict(data["request"]),
            response=Response.from_dict(resp) if resp else None,
            error=data.get("error"),
            created_at=data.get("created_at", 0.0),
            duration_ms=data.get("duration_ms"),
        )
