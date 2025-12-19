from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

MonitorStatus = Literal["STOPPED", "RUNNING"]


@dataclass(frozen=True)
class MonitorConfig:
    tracked_exe_names: list[str]
    poll_interval_ms: int
    end_debounce_ms: int


@dataclass
class MonitorState:
    status: MonitorStatus = "STOPPED"
    active_exe: Optional[str] = None
    missing_since_ms: Optional[int] = None
