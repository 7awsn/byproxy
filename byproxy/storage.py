"""Histórico de flows em memória, com salvar/carregar em disco."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from .flow import Flow


class FlowStore:
    def __init__(self) -> None:
        self._flows: list[Flow] = []
        self._lock = threading.Lock()
        self._counter = 0

    def next_id(self) -> int:
        with self._lock:
            self._counter += 1
            return self._counter

    def add(self, flow: Flow) -> None:
        with self._lock:
            self._flows.append(flow)

    def all(self) -> list[Flow]:
        with self._lock:
            return list(self._flows)

    def get(self, flow_id: int) -> Flow | None:
        with self._lock:
            for flow in self._flows:
                if flow.id == flow_id:
                    return flow
            return None

    def filter(self, needle: str) -> list[Flow]:
        """Filtra pelo texto na URL (sem diferenciar maiúsculas)."""
        needle = needle.lower()
        with self._lock:
            return [f for f in self._flows if needle in f.request.url.lower()]

    def clear(self) -> None:
        with self._lock:
            self._flows.clear()

    def save(self, path: str | Path) -> int:
        with self._lock:
            data = [f.to_dict() for f in self._flows]
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        return len(data)

    def load(self, path: str | Path) -> int:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        flows = [Flow.from_dict(item) for item in data]
        with self._lock:
            self._flows = flows
            self._counter = max((f.id for f in flows), default=0)
        return len(flows)
