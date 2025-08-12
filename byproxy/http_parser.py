"""Funções auxiliares de HTTP.

Aqui ficam coisas pequenas e isoladas: separar host de porta, remover
cabeçalhos ponto-a-ponto e converter uma requisição de/para o formato de
texto editável (usado quando o usuário edita uma requisição pausada).
"""

from __future__ import annotations

from .flow import HOP_BY_HOP, Request


def split_authority(authority: str, default_port: int) -> tuple[str, int]:
    """Separa "host:porta" em (host, porta).

    Lida com endereços IPv6 entre colchetes, ex.: "[::1]:8080".
    """
    authority = authority.strip()
    if authority.startswith("["):
        # IPv6 literal: o host vai dentro dos colchetes.
        end = authority.find("]")
        host = authority[1:end]
        rest = authority[end + 1 :]
        if rest.startswith(":"):
            return host, int(rest[1:])
        return host, default_port
    if ":" in authority:
        host, _, port = authority.rpartition(":")
        return host, int(port)
    return authority, default_port


def strip_hop_by_hop(headers: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Devolve os cabeçalhos sem os que não devem ser repassados."""
    return [(k, v) for k, v in headers if k.lower() not in HOP_BY_HOP]


def request_to_editable(req: Request) -> str:
    """Serializa a requisição em texto, no formato que o usuário edita.

    O formato lembra uma requisição HTTP crua, mas usa a origin-form
    (apenas o caminho na linha inicial), já que host e esquema são fixos.
    """
    lines = [f"{req.method} {req.path} {req.http_version}"]
    for key, value in req.headers:
        lines.append(f"{key}: {value}")
    head = "\r\n".join(lines)
    # O corpo é mostrado como texto (melhor esforço em UTF-8).
    body = req.body.decode("utf-8", errors="replace")
    return f"{head}\r\n\r\n{body}"


def parse_editable(text: str) -> tuple[str, str, list[tuple[str, str]], bytes]:
    """Lê o texto editado e devolve (método, caminho, cabeçalhos, corpo).

    Aceita tanto \r\n quanto \n como separador de linha.
    """
    normalized = text.replace("\r\n", "\n")
    if "\n\n" in normalized:
        head, _, body_text = normalized.partition("\n\n")
    else:
        head, body_text = normalized, ""

    head_lines = head.split("\n")
    if not head_lines or not head_lines[0].strip():
        raise ValueError("linha de requisição ausente")

    parts = head_lines[0].split()
    if len(parts) < 2:
        raise ValueError("linha de requisição inválida")
    method = parts[0]
    path = parts[1]

    headers: list[tuple[str, str]] = []
    for line in head_lines[1:]:
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"cabeçalho inválido: {line!r}")
        key, _, value = line.partition(":")
        headers.append((key.strip(), value.strip()))

    return method, path, headers, body_text.encode("utf-8")
