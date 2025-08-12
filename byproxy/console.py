"""Console interativo que roda junto com o proxy.

O servidor fica em uma thread de fundo capturando tráfego; este laço lê
comandos do usuário e mostra o histórico, detalhes, filtros e controla a
interceptação.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import threading

from . import ui
from .ca import CertificateAuthority
from .flow import Request
from .http_parser import parse_editable, request_to_editable
from .interceptor import Interceptor
from .proxy import ProxyServer
from .storage import FlowStore
from .ui import console

HELP = """
[bold]Comandos[/bold]
  [cyan]history[/cyan] [i]([/i]ou [cyan]ls[/cyan][i])[/i]        lista o tráfego capturado
  [cyan]inspect <#>[/cyan]           mostra requisição e resposta de um flow
  [cyan]filter <texto>[/cyan]        lista apenas flows cuja URL contém o texto
  [cyan]intercept on|off[/cyan]      liga/desliga a pausa de requisições
  [cyan]queue[/cyan]                 lista as requisições pausadas
  [cyan]edit <#>[/cyan]              edita uma requisição pausada no editor
  [cyan]forward <#>[/cyan] | [cyan]forward all[/cyan]   encaminha requisição(ões) pausada(s)
  [cyan]drop <#>[/cyan]              descarta uma requisição pausada
  [cyan]save <arquivo>[/cyan]        salva a sessão em JSON
  [cyan]load <arquivo>[/cyan]        carrega uma sessão salva
  [cyan]clear[/cyan]                 limpa o histórico
  [cyan]ca[/cyan]                    mostra onde está o certificado da CA
  [cyan]help[/cyan]                  mostra esta ajuda
  [cyan]quit[/cyan] [i]([/i]ou [cyan]exit[/cyan][i])[/i]          encerra o proxy
""".strip()


class Console:
    def __init__(self, host: str, port: int):
        self.store = FlowStore()
        self.interceptor = Interceptor()
        self.ca = CertificateAuthority()
        self.server = ProxyServer((host, port), self.store, self.interceptor, self.ca)
        self.host = host
        self.port = port
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    def run(self) -> None:
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()
        self._banner()
        try:
            self._loop()
        finally:
            self.interceptor.release_all()
            self.server.shutdown()
            self.server.server_close()

    def _banner(self) -> None:
        console.print(
            f"[bold green]byproxy[/bold green] ouvindo em "
            f"[bold]{self.host}:{self.port}[/bold]  "
            f"[dim](digite 'help' para os comandos)[/dim]"
        )
        console.print(f"[dim]CA: {self.ca.ca_cert_path}[/dim]")

    def _loop(self) -> None:
        while True:
            try:
                raw = input("byproxy> ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print()
                return
            if not raw:
                continue
            command, _, rest = raw.partition(" ")
            rest = rest.strip()
            if command in ("quit", "exit"):
                return
            try:
                self._dispatch(command, rest)
            except Exception as exc:  # um comando com erro não derruba o console
                console.print(f"[red]erro:[/red] {exc}")

    # ------------------------------------------------------------------
    def _dispatch(self, command: str, rest: str) -> None:
        if command in ("history", "ls"):
            ui.render_history(self.store.all())
        elif command == "inspect":
            self._inspect(rest)
        elif command == "filter":
            if not rest:
                console.print("[yellow]uso: filter <texto>[/yellow]")
                return
            ui.render_history(self.store.filter(rest), title=f"Filtro: {rest}")
        elif command == "intercept":
            self._intercept(rest)
        elif command == "queue":
            ui.render_pending(self.interceptor.pending_list())
        elif command == "edit":
            self._edit(rest)
        elif command == "forward":
            self._forward(rest)
        elif command == "drop":
            self._drop(rest)
        elif command == "save":
            self._save(rest)
        elif command == "load":
            self._load(rest)
        elif command == "clear":
            self.store.clear()
            console.print("[dim]histórico limpo.[/dim]")
        elif command == "ca":
            console.print(f"Certificado da CA: [bold]{self.ca.ca_cert_path}[/bold]")
            console.print("[dim]Importe-o como autoridade confiável para inspecionar HTTPS.[/dim]")
        elif command == "help":
            console.print(HELP)
        else:
            console.print(f"[yellow]comando desconhecido:[/yellow] {command} [dim](help)[/dim]")

    # ------------------------------------------------------------------
    def _inspect(self, rest: str) -> None:
        flow = self.store.get(_as_id(rest))
        if flow is None:
            console.print("[yellow]flow não encontrado.[/yellow]")
            return
        ui.render_flow(flow)

    def _intercept(self, rest: str) -> None:
        if rest == "on":
            self.interceptor.enabled = True
            console.print("[green]interceptação ligada.[/green] Novas requisições ficam pausadas (veja 'queue').")
        elif rest == "off":
            self.interceptor.enabled = False
            self.interceptor.forward_all()
            console.print("[green]interceptação desligada.[/green] Requisições pausadas foram encaminhadas.")
        else:
            console.print("[yellow]uso: intercept on|off[/yellow]")

    def _edit(self, rest: str) -> None:
        pending = self.interceptor.get(_as_id(rest))
        if pending is None:
            console.print("[yellow]nenhuma requisição pausada com esse número.[/yellow]")
            return
        edited = _open_editor(request_to_editable(pending.request))
        method, path, headers, body = parse_editable(edited)
        base = pending.request
        new_request = Request(
            method=method,
            scheme=base.scheme,
            host=base.host,
            port=base.port,
            path=path,
            http_version=base.http_version,
            headers=headers,
            body=body,
        )
        # Mantém o Content-Length coerente com o corpo editado.
        new_request.headers = _fix_content_length(new_request.headers, len(body))
        pending.request = new_request
        console.print(f"[green]requisição #{pending.flow.id} atualizada.[/green] Use 'forward {pending.flow.id}'.")

    def _forward(self, rest: str) -> None:
        if rest == "all":
            count = self.interceptor.forward_all()
            console.print(f"[green]{count}[/green] requisição(ões) encaminhada(s).")
            return
        if self.interceptor.forward(_as_id(rest)):
            console.print("[green]encaminhada.[/green]")
        else:
            console.print("[yellow]nenhuma requisição pausada com esse número.[/yellow]")

    def _drop(self, rest: str) -> None:
        if self.interceptor.drop(_as_id(rest)):
            console.print("[green]descartada.[/green]")
        else:
            console.print("[yellow]nenhuma requisição pausada com esse número.[/yellow]")

    def _save(self, rest: str) -> None:
        if not rest:
            console.print("[yellow]uso: save <arquivo>[/yellow]")
            return
        count = self.store.save(rest)
        console.print(f"[green]{count}[/green] flow(s) salvos em [bold]{rest}[/bold].")

    def _load(self, rest: str) -> None:
        if not rest:
            console.print("[yellow]uso: load <arquivo>[/yellow]")
            return
        count = self.store.load(rest)
        console.print(f"[green]{count}[/green] flow(s) carregados de [bold]{rest}[/bold].")


# ----------------------------------------------------------------------
# Auxiliares
# ----------------------------------------------------------------------
def _as_id(rest: str) -> int:
    try:
        return int(rest.strip())
    except ValueError as exc:
        raise ValueError(f"número inválido: {rest!r}") from exc


def _fix_content_length(headers: list[tuple[str, str]], length: int) -> list[tuple[str, str]]:
    result = [(k, v) for k, v in headers if k.lower() != "content-length"]
    if length:
        result.append(("Content-Length", str(length)))
    return result


def _open_editor(text: str) -> str:
    """Abre o texto num editor externo e devolve o conteúdo salvo."""
    editor = os.environ.get("EDITOR")
    if not editor:
        editor = "notepad" if os.name == "nt" else "nano"
    with tempfile.NamedTemporaryFile("w+", suffix=".txt", delete=False, encoding="utf-8") as handle:
        handle.write(text)
        path = handle.name
    try:
        subprocess.call([editor, path])
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
