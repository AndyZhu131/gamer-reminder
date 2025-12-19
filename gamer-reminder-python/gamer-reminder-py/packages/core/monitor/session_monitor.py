from __future__ import annotations

import threading
import time
import logging
from typing import Callable, Optional

from .types import MonitorConfig, MonitorState
from .process_detector import running_exe_names_lower
from .resource_heuristic import ResourceHeuristic, NoopResourceHeuristic


log = logging.getLogger(__name__)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


class SessionMonitor:
    """Background monitor that emits GAME_STARTED / GAME_ENDED based on process polling."""

    def __init__(self, config: dict, resource_heuristic: Optional[ResourceHeuristic] = None) -> None:
        self._cfg = MonitorConfig(**config)
        self._heur = resource_heuristic or NoopResourceHeuristic()
        self._state = MonitorState()
        self._lock = threading.Lock()

        self._event_cb: Optional[Callable[[dict], None]] = None
        self._error_cb: Optional[Callable[[str], None]] = None

        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()

    def on_event(self, cb: Callable[[dict], None]) -> None:
        self._event_cb = cb

    def on_error(self, cb: Callable[[str], None]) -> None:
        self._error_cb = cb

    def update_config(self, config: dict) -> None:
        with self._lock:
            self._cfg = MonitorConfig(**config)

    def get_state(self) -> MonitorState:
        with self._lock:
            return MonitorState(
                status=self._state.status,
                active_exe=self._state.active_exe,
                missing_since_ms=self._state.missing_since_ms,
            )

    def start(self) -> None:
        with self._lock:
            if self._state.status == "RUNNING":
                return
            self._state.status = "RUNNING"
            self._state.active_exe = None
            self._state.missing_since_ms = None

        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._run, name="SessionMonitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_evt.set()
        with self._lock:
            self._state.status = "STOPPED"
            self._state.active_exe = None
            self._state.missing_since_ms = None

    def _emit(self, evt: dict) -> None:
        if self._event_cb:
            self._event_cb(evt)

    def _emit_error(self, msg: str) -> None:
        if self._error_cb:
            self._error_cb(msg)

    def _pick_active(self, running: set[str], tracked: list[str]) -> Optional[str]:
        for exe in [t.strip().lower() for t in tracked if t.strip()]:
            if exe in running:
                return exe
        return None

    def _run(self) -> None:
        while not self._stop_evt.is_set():
            try:
                with self._lock:
                    cfg = self._cfg
                    state = self._state

                running = running_exe_names_lower()
                active = self._pick_active(running, cfg.tracked_exe_names)

                if state.active_exe is None:
                    if active:
                        with self._lock:
                            self._state.active_exe = active
                            self._state.missing_since_ms = None
                        self._emit({"type": "GAME_STARTED", "exe": active, "at": _now_iso(), "reason": None})
                    time.sleep(cfg.poll_interval_ms / 1000.0)
                    continue

                current = state.active_exe

                if current in running:
                    with self._lock:
                        self._state.missing_since_ms = None
                    time.sleep(cfg.poll_interval_ms / 1000.0)
                    continue

                now_ms = int(time.time() * 1000)
                if state.missing_since_ms is None:
                    with self._lock:
                        self._state.missing_since_ms = now_ms
                    time.sleep(cfg.poll_interval_ms / 1000.0)
                    continue

                missing_for = now_ms - int(state.missing_since_ms)
                if missing_for >= cfg.end_debounce_ms:
                    self._emit({"type": "GAME_ENDED", "exe": current, "at": _now_iso(), "reason": "PROCESS_EXIT_DEBOUNCED"})
                    with self._lock:
                        self._state.active_exe = None
                        self._state.missing_since_ms = None
                    time.sleep(cfg.poll_interval_ms / 1000.0)
                    continue

                if self._heur.should_treat_as_ended(current, cfg):
                    self._emit({"type": "GAME_ENDED", "exe": current, "at": _now_iso(), "reason": "RESOURCE_HEURISTIC"})
                    with self._lock:
                        self._state.active_exe = None
                        self._state.missing_since_ms = None

                time.sleep(cfg.poll_interval_ms / 1000.0)

            except Exception as e:
                log.exception("Monitor loop error")
                self._emit_error(str(e))
                time.sleep(1.0)
