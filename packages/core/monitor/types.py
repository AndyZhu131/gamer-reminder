from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

MonitorStatus = Literal["STOPPED", "RUNNING"]


@dataclass
class MonitorState:
    """
    Legacy state format for UI compatibility.
    Maps hardware monitor state to a format compatible with existing UI code.
    """
    status: MonitorStatus = "STOPPED"
    active_exe: Optional[str] = None  # Repurposed: stores activity_state when RUNNING
    missing_since_ms: Optional[int] = None  # Repurposed: stores suspect_inactive_since_ms
