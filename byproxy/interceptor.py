"""Interceptação de requisições.

Quando a interceptação está ligada, cada requisição que chega fica em
espera até o usuário decidir o que fazer: encaminhar (eventualmente
editada) ou descartar. Como o proxy roda em threads e o console no fio
principal, a sincronização é feita com um Event por requisição pausada.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass

from .flow import Flow, Request


@dataclass
class Pending:
    flow: Flow
    event: threading.Event
    request: Request  # requisição atual (pode ser editada antes de encaminhar)
    decision: str | None = None  # "forward" ou "drop"


class Interceptor:
    def __init__(self) -> None:
        self.enabled = False
        self._pending: "OrderedDict[int, Pending]" = OrderedDict()
        self._lock = threading.Lock()

    def handle(self, flow: Flow) -> Request | None:
        """Chamado pela thread do proxy. Bloqueia enquanto a requisição
        estiver pausada. Devolve a requisição a encaminhar, ou None para
        descartar.
        """
        if not self.enabled:
            return flow.request

        pending = Pending(flow=flow, event=threading.Event(), request=flow.request)
        with self._lock:
            self._pending[flow.id] = pending

        pending.event.wait()

        with self._lock:
            self._pending.pop(flow.id, None)

        if pending.decision == "drop":
            return None
        return pending.request

    # ------------------------------------------------------------------
    # Operações usadas pelo console
    # ------------------------------------------------------------------
    def pending_list(self) -> list[Pending]:
        with self._lock:
            return list(self._pending.values())

    def get(self, flow_id: int) -> Pending | None:
        with self._lock:
            return self._pending.get(flow_id)

    def forward(self, flow_id: int, request: Request | None = None) -> bool:
        with self._lock:
            pending = self._pending.get(flow_id)
            if pending is None:
                return False
            if request is not None:
                pending.request = request
            pending.decision = "forward"
            pending.event.set()
            return True

    def forward_all(self) -> int:
        with self._lock:
            items = list(self._pending.values())
            for pending in items:
                pending.decision = "forward"
                pending.event.set()
            return len(items)

    def drop(self, flow_id: int) -> bool:
        with self._lock:
            pending = self._pending.get(flow_id)
            if pending is None:
                return False
            pending.decision = "drop"
            pending.event.set()
            return True

    def release_all(self) -> None:
        """Libera tudo que estiver pausado (usado ao desligar o proxy)."""
        with self._lock:
            for pending in self._pending.values():
                if pending.decision is None:
                    pending.decision = "forward"
                pending.event.set()
