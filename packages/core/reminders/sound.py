from __future__ import annotations

import logging
from typing import Protocol

log = logging.getLogger(__name__)


class SoundPlayer(Protocol):
    def play(self) -> None:
        ...


class WinBeepSound:
    def play(self) -> None:
        try:
            import winsound
            winsound.Beep(900, 180)
        except Exception:
            log.exception("Failed to play sound")
