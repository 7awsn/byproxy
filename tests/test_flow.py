from byproxy.flow import Flow, Request, Response


def test_url_omite_porta_padrao():
    req = Request(method="GET", scheme="https", host="site.com", port=443, path="/x")
    assert req.url == "https://site.com/x"


def test_url_mostra_porta_nao_padrao():
    req = Request(method="GET", scheme="http", host="site.com", port=8080, path="/")
    assert req.url == "http://site.com:8080/"


def test_header_case_insensitive():
    req = Request(
        method="GET", scheme="http", host="x", port=80, path="/",
        headers=[("Content-Type", "text/html")],
    )
    assert req.header("content-type") == "text/html"
    assert req.header("X-Nao-Existe") is None


def test_flow_round_trip_preserva_corpo_binario():
    req = Request(method="POST", scheme="http", host="x", port=80, path="/", body=b"\x00\x01\x02")
    resp = Response(status_code=200, reason="OK", body=b"\xff\xfe")
    flow = Flow(id=7, request=req, response=resp, duration_ms=12.5)

    restored = Flow.from_dict(flow.to_dict())
    assert restored.id == 7
    assert restored.request.body == b"\x00\x01\x02"
    assert restored.response.body == b"\xff\xfe"
    assert restored.duration_ms == 12.5
