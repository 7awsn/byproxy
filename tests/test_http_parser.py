from byproxy.flow import Request
from byproxy.http_parser import (
    parse_editable,
    request_to_editable,
    split_authority,
    strip_hop_by_hop,
)


def test_split_authority_com_porta():
    assert split_authority("example.com:8443", 443) == ("example.com", 8443)


def test_split_authority_sem_porta_usa_padrao():
    assert split_authority("example.com", 443) == ("example.com", 443)


def test_split_authority_ipv6():
    assert split_authority("[::1]:8080", 443) == ("::1", 8080)
    assert split_authority("[::1]", 443) == ("::1", 443)


def test_strip_hop_by_hop_remove_connection():
    headers = [("Host", "x"), ("Connection", "keep-alive"), ("Proxy-Connection", "x")]
    assert strip_hop_by_hop(headers) == [("Host", "x")]


def test_parse_editable_round_trip():
    req = Request(
        method="POST",
        scheme="https",
        host="api.site.com",
        port=443,
        path="/login?next=/home",
        headers=[("Host", "api.site.com"), ("Content-Type", "application/json")],
        body=b'{"user":"a"}',
    )
    method, path, headers, body = parse_editable(request_to_editable(req))
    assert method == "POST"
    assert path == "/login?next=/home"
    assert ("Content-Type", "application/json") in headers
    assert body == b'{"user":"a"}'


def test_parse_editable_aceita_lf():
    texto = "GET / HTTP/1.1\nHost: x\n\n"
    method, path, headers, body = parse_editable(texto)
    assert method == "GET"
    assert path == "/"
    assert headers == [("Host", "x")]
    assert body == b""
