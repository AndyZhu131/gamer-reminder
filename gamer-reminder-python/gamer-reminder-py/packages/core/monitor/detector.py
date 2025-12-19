from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class HardwareMetrics:
    """Current hardware utilization metrics."""
    gpu_utilization: Optional[float]  # 0-100, None if unavailable
    cpu_utilization: float  # 0-100
    timestamp_ms: int


class ActivityDetector(ABC):
    """Interface for detecting gaming activity based on hardware usage."""

    @abstractmethod
    def sample(self) -> HardwareMetrics:
        """Sample current hardware metrics. Must be thread-safe."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this detector can provide metrics (e.g., GPU available)."""
        ...

