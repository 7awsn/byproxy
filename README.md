# byproxy

Um proxy HTTP/HTTPS interceptador que roda inteiro no terminal. A ideia é a
mesma de ferramentas como Burp Suite e Charles! Ver, pausar e modificar o
tráfego entre um cliente e um servidor — mas sem interface gráfica: tudo por
linha de comando.

O encaminhamento é escrito à mão em cima da biblioteca padrão do Python. Para
HTTPS o proxy termina a conexão TLS do cliente usando uma autoridade
certificadora local, inspeciona a requisição e reabre a conexão com o destino.

> Use apenas em dispositivos e ambientes que você tem autorização para testar.

## Arquitetura

```
   cliente (navegador / curl)
            │
            ▼
   ┌───────────────────┐        captura   ┌────────────┐
   │     byproxy        │ ───────────────▶ │  histórico  │
   │  captura → pausa   │                  └────────────┘
   │  → modifica → envia│ ◀───┐
   └───────────────────┘      │ pausa (interceptação)
            │                 │
            ▼            console interativo
   servidor de destino
```

- **Captura**: método, URL, cabeçalhos e corpo da requisição; status, cabeçalhos
  e corpo da resposta.
- **Interceptação**: pausa a requisição, deixa editar cabeçalhos/parâmetros/corpo
  e então encaminha (ou descarta).
- **Inspeção**: histórico em tabela, filtro por URL, detalhe de um flow e
  salvar/carregar a sessão em JSON.

## Instalação

```bash
pip install -e .
```

Requer Python 3.10+.

## Uso

Inicie o proxy e o console:

```bash
byproxy start --host 127.0.0.1 --port 8080
```

Aponte o cliente para `127.0.0.1:8080`. Por exemplo, com `curl`:

```bash
curl -x http://127.0.0.1:8080 http://exemplo.com/
```

Dentro do console:

```
byproxy> history            # lista o tráfego
byproxy> inspect 3          # detalhe do flow 3
byproxy> filter login       # só URLs com "login"
byproxy> intercept on       # passa a pausar requisições
byproxy> queue              # lista as pausadas
byproxy> edit 5             # edita a requisição 5 no editor
byproxy> forward 5          # encaminha
byproxy> save sessao.json   # salva a sessão
```

### HTTPS

Para inspecionar HTTPS o cliente precisa confiar na CA local. O caminho do
certificado aparece ao iniciar o proxy (ou rode `byproxy ca-path`); importe-o
como autoridade confiável no sistema ou no navegador. Enquanto a CA não for
confiada, conexões HTTPS vão falhar no handshake, isso é esperado.

```bash
byproxy ca-path   # mostra onde está o certificado da CA
```

## Testar localmente

Um servidor de eco acompanha o projeto. Ele devolve em JSON tudo que recebe,
o que ajuda a confirmar que suas edições chegaram ao destino:

```bash
python examples/test_server.py
# em outro terminal:
curl -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

## Comandos do console

| Comando | O que faz |
| --- | --- |
| `history` / `ls` | lista o tráfego capturado |
| `inspect <#>` | mostra requisição e resposta |
| `filter <texto>` | filtra o histórico pela URL |
| `intercept on\|off` | liga/desliga a pausa de requisições |
| `queue` | lista as requisições pausadas |
| `edit <#>` | edita uma requisição pausada |
| `forward <#>` / `forward all` | encaminha requisição(ões) pausada(s) |
| `drop <#>` | descarta uma requisição pausada |
| `save` / `load <arquivo>` | salva/carrega a sessão em JSON |
| `clear` | limpa o histórico |
| `ca` | mostra o caminho do certificado da CA |
| `quit` / `exit` | encerra |

## Testes

```bash
pip install -e ".[dev]"
pytest
```

## Licença

MIT. Veja [LICENSE](LICENSE).
