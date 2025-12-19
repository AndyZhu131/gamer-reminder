from __future__ import annotations

import logging
from typing import Protocol
from win10toast import ToastNotifier

log = logging.getLogger(__name__)


class Notifier(Protocol):
    def notify(self, title: str, body: str) -> None:
        ...


class ToastNotifierWin10:
    def __init__(self) -> None:
        self._toaster = ToastNotifier()

    def notify(self, title: str, body: str) -> None:
        try:
            self._toaster.show_toast(title, body, duration=6, threaded=True)
        except Exception:
            log.exception("Failed to show toast notification")
