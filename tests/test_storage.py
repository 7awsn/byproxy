from byproxy.flow import Flow, Request, Response
from byproxy.storage import FlowStore


def _make_flow(store: FlowStore, host: str, status: int) -> Flow:
    req = Request(method="GET", scheme="http", host=host, port=80, path="/")
    resp = Response(status_code=status, reason="OK", body=b"hi")
    flow = Flow(id=store.next_id(), request=req, response=resp)
    store.add(flow)
    return flow


def test_add_e_all():
    store = FlowStore()
    _make_flow(store, "a.com", 200)
    _make_flow(store, "b.com", 404)
    assert len(store.all()) == 2


def test_ids_incrementais():
    store = FlowStore()
    f1 = _make_flow(store, "a.com", 200)
    f2 = _make_flow(store, "b.com", 200)
    assert f2.id == f1.id + 1


def test_filter_por_url():
    store = FlowStore()
    _make_flow(store, "api.site.com", 200)
    _make_flow(store, "cdn.outra.com", 200)
    assert len(store.filter("site")) == 1


def test_save_e_load_round_trip(tmp_path):
    store = FlowStore()
    _make_flow(store, "a.com", 200)
    _make_flow(store, "b.com", 500)
    destino = tmp_path / "sessao.json"
    store.save(destino)

    novo = FlowStore()
    assert novo.load(destino) == 2
    flows = novo.all()
    assert flows[0].request.host == "a.com"
    assert flows[1].response.status_code == 500
    # O contador continua a partir do maior id carregado.
    assert novo.next_id() == 3
