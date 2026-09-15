"""
Token de cancelamento cooperativo. threading.Event é thread-safe por
natureza — usado tanto pelo worker Qt quanto pelos testes de domain
puro (que não têm QThread disponível).
"""
from __future__ import annotations

import threading


class CancelToken:
    def __init__(self):
        self._event = threading.Event()

    def set(self) -> None:
        self._event.set()

    def is_set(self) -> bool:
        return self._event.is_set()

    def reset(self) -> None:
        self._event.clear()
