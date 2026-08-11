from byproxy.console import _fix_content_length, _set_header


def test_set_header_adiciona_novo():
    headers = [("Host", "x")]
    assert _set_header(headers, "X-Teste", "1") == [("Host", "x"), ("X-Teste", "1")]


def test_set_header_substitui_no_lugar_case_insensitive():
    headers = [("Host", "x"), ("User-Agent", "antigo"), ("Accept", "*/*")]
    out = _set_header(headers, "user-agent", "novo")
    assert out == [("Host", "x"), ("user-agent", "novo"), ("Accept", "*/*")]


def test_set_header_sem_valor_remove():
    headers = [("Host", "x"), ("Cookie", "a=1")]
    assert _set_header(headers, "cookie", "") == [("Host", "x")]


def test_fix_content_length_substitui():
    headers = [("Content-Length", "10"), ("Host", "x")]
    out = _fix_content_length(headers, 3)
    assert ("Content-Length", "3") in out
    assert sum(1 for k, _ in out if k.lower() == "content-length") == 1


def test_fix_content_length_zero_remove():
    headers = [("Content-Length", "10"), ("Host", "x")]
    assert _fix_content_length(headers, 0) == [("Host", "x")]
