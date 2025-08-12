"""Renderização no terminal com a biblioteca rich."""

from __future__ import annotations

import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .flow import Flow
from .interceptor import Pending

console = Console()


def _status_style(status: int | None) -> str:
    if status is None:
        return "dim"
    if status < 300:
        return "green"
    if status < 400:
        return "cyan"
    if status < 500:
        return "yellow"
    return "red"


def _clock(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")


def render_history(flows: list[Flow], title: str = "Histórico") -> None:
    if not flows:
        console.print("[dim]Nenhuma requisição capturada ainda.[/dim]")
        return

    table = Table(title=title, header_style="bold", expand=True)
    table.add_column("#", justify="right", style="bold")
    table.add_column("Hora", style="dim", no_wrap=True)
    table.add_column("Método", no_wrap=True)
    table.add_column("Status", justify="right", no_wrap=True)
    table.add_column("Host", no_wrap=True)
    table.add_column("Caminho", overflow="ellipsis", max_width=40)
    table.add_column("Tam.", justify="right", no_wrap=True)
    table.add_column("ms", justify="right", no_wrap=True)

    for flow in flows:
        status = flow.response.status_code if flow.response else None
        status_text = Text(str(status) if status else (flow.error or "-"), style=_status_style(status))
        size = len(flow.response.body) if flow.response else 0
        duration = f"{flow.duration_ms:.0f}" if flow.duration_ms else "-"
        table.add_row(
            str(flow.id),
            _clock(flow.created_at),
            flow.request.method,
            status_text,
            flow.request.host,
            flow.request.path,
            _human_size(size),
            duration,
        )
    console.print(table)


def render_flow(flow: Flow) -> None:
    req = flow.request
    req_lines = [f"[bold]{req.method}[/bold] {req.url}", f"[dim]{req.http_version}[/dim]", ""]
    for key, value in req.headers:
        req_lines.append(f"[cyan]{key}[/cyan]: {value}")
    if req.body:
        req_lines.append("")
        req_lines.append(_preview_body(req.body))
    console.print(Panel("\n".join(req_lines), title=f"Requisição #{flow.id}", border_style="blue"))

    if flow.error and not flow.response:
        console.print(Panel(f"[red]{flow.error}[/red]", title="Erro", border_style="red"))
        return

    resp = flow.response
    if resp is None:
        console.print("[dim]Sem resposta registrada.[/dim]")
        return

    style = _status_style(resp.status_code)
    resp_lines = [f"[{style}]{resp.status_code} {resp.reason}[/{style}]", ""]
    for key, value in resp.headers:
        resp_lines.append(f"[cyan]{key}[/cyan]: {value}")
    if resp.body:
        resp_lines.append("")
        resp_lines.append(_preview_body(resp.body))
    console.print(Panel("\n".join(resp_lines), title=f"Resposta #{flow.id}", border_style="green"))


def render_pending(items: list[Pending]) -> None:
    if not items:
        console.print("[dim]Nenhuma requisição pausada.[/dim]")
        return
    table = Table(title="Requisições pausadas", header_style="bold yellow")
    table.add_column("#", justify="right")
    table.add_column("Método")
    table.add_column("URL", overflow="ellipsis", max_width=70)
    for pending in items:
        table.add_row(str(pending.flow.id), pending.request.method, pending.request.url)
    console.print(table)


def _preview_body(body: bytes, limit: int = 2000) -> str:
    text = body.decode("utf-8", errors="replace")
    if len(text) > limit:
        text = text[:limit] + f"\n[dim]... (+{len(text) - limit} caracteres)[/dim]"
    return text


def _human_size(num: int) -> str:
    size = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"
