# byproxy

![tests](https://github.com/7awsn/byproxy/actions/workflows/tests.yml/badge.svg)

**English** | [Português](/7awsn/byproxy/blob/main/README.pt-br.md)

A console HTTP/HTTPS intercepting proxy that runs entirely in the terminal.
Same idea as tools like Burp Suite and Charles: view, pause and modify the
traffic between a client and a server, but with no GUI, all from the command
line.

Forwarding is written by hand on top of the Python standard library. For HTTPS
the proxy terminates the client's TLS connection using a local certificate
authority, inspects the request and opens a fresh connection to the target.

> Use only on devices and environments you are authorized to test.

## Architecture

```
   client (browser / curl)
            │
            ▼
   ┌───────────────────┐        capture   ┌────────────┐
   │     byproxy        │ ───────────────▶ │  history    │
   │  capture → pause   │                  └────────────┘
   │  → modify → send   │ ◀───┐
   └───────────────────┘      │ pause (interception)
            │                 │
            ▼           interactive console
       target server
```

- **Capture**: request method, URL, headers and body; response status, headers
  and body.
- **Interception**: pause a request, edit headers/params/body, then forward
  (or drop) it.
- **Inspection**: history table, filter by URL, detail of a flow, and
  save/load the session as JSON.

## Installation

```bash
pip install -e .
```

Requires Python 3.10+.

## Usage

Start the proxy and the console:

```bash
byproxy start --host 127.0.0.1 --port 8080
```

Point the client at `127.0.0.1:8080`. For example, with `curl`:

```bash
curl -x http://127.0.0.1:8080 http://example.com/
```

Inside the console:

```
byproxy> history            # list the traffic
byproxy> inspect 3          # detail of flow 3
byproxy> filter login       # only URLs containing "login"
byproxy> intercept on       # start pausing requests
byproxy> queue              # list the paused ones
byproxy> set-header 5 User-Agent curl/8.0   # edit right in the console
byproxy> set-body 5 {"user":"admin"}
byproxy> forward 5          # forward it
byproxy> save session.json  # save the session
```

A paused request can be edited right in the console (`set-method`, `set-path`,
`set-header`, `set-body`) or opened in full in an external editor with
`edit <#>`.

### HTTPS

To inspect HTTPS the client must trust the local CA. The certificate path is
shown when the proxy starts (or run `byproxy ca-path`); import it as a trusted
authority in the system or browser. Until the CA is trusted, HTTPS connections
will fail the handshake, which is expected.

```bash
byproxy ca-path   # show the CA certificate path
```

## Testing locally

An echo server ships with the project. It returns everything it receives as
JSON, which helps confirm your edits reached the target:

```bash
python examples/test_server.py
# in another terminal:
curl -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

## Console commands

| Command | What it does |
| --- | --- |
| `history` / `ls` | list captured traffic |
| `inspect <#>` | show request and response |
| `filter <text>` | filter history by URL |
| `intercept on\|off` | toggle pausing of requests |
| `queue` | list paused requests |
| `edit <#>` | edit a paused request in an external editor |
| `set-method <#> <m>` | change the method of a paused request |
| `set-path <#> <path>` | change the path/query of a paused request |
| `set-header <#> <name> [value]` | set (or remove, if no value) a header |
| `set-body <#> [text]` | replace the body (empty clears it) |
| `forward <#>` / `forward all` | forward paused request(s) |
| `drop <#>` | drop a paused request |
| `save` / `load <file>` | save/load the session as JSON |
| `clear` | clear the history |
| `ca` | show the CA certificate path |
| `quit` / `exit` | exit |

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT. See [LICENSE](LICENSE).
