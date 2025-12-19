from __future__ import annotations

from typing import Protocol
from .types import MonitorConfig


class ResourceHeuristic(Protocol):
    """Placeholder interface for future CPU/GPU heuristics.

    TODO: Implement a Windows resource heuristic using PerfCounters/ETW/vendor APIs.
    """

    def should_treat_as_ended(self, exe: str, config: MonitorConfig) -> bool:
        ...


class NoopResourceHeuristic:
    def should_treat_as_ended(self, exe: str, config: MonitorConfig) -> bool:
        return False
