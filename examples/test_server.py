"""Servidor HTTP local simples, para testar o proxy sem sair da máquina.

Suba com:
    python examples/test_server.py

Depois aponte o cliente para o proxy e acesse http://127.0.0.1:9000/.
Ele devolve em JSON tudo que recebeu (método, caminho, cabeçalhos, corpo),
o que é útil para ver suas edições de requisição chegando ao destino.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class EchoHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        return

    def _echo(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b""
        payload = json.dumps(
            {
                "method": self.command,
                "path": self.path,
                "headers": dict(self.headers.items()),
                "body": body.decode("utf-8", errors="replace"),
            },
            indent=2,
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = _echo
    do_POST = _echo
    do_PUT = _echo
    do_DELETE = _echo


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 9000), EchoHandler)
    print("servidor de teste em http://127.0.0.1:9000/  (Ctrl+C para sair)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
