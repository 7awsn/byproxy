"""Interface de linha de comando (entrada do programa)."""

from __future__ import annotations

import typer

from . import __version__
from .ca import CertificateAuthority

app = typer.Typer(
    add_completion=False,
    help="Proxy HTTP/HTTPS interceptador para o terminal.",
    no_args_is_help=True,
)


@app.command()
def start(
    host: str = typer.Option("127.0.0.1", help="Endereço onde o proxy escuta."),
    port: int = typer.Option(8080, help="Porta do proxy."),
) -> None:
    """Inicia o proxy e abre o console interativo."""
    # Importado aqui para manter o start do CLI leve.
    from .console import Console

    Console(host, port).run()


@app.command("ca-path")
def ca_path() -> None:
    """Mostra o caminho do certificado da CA local."""
    ca = CertificateAuthority()
    typer.echo(str(ca.ca_cert_path))


@app.command()
def version() -> None:
    """Mostra a versão instalada."""
    typer.echo(__version__)
