from __future__ import annotations

from typing import List
from pydantic import BaseModel, Field


class ReminderMessage(BaseModel):
    id: str = Field(default_factory=lambda: "r_" + __import__("uuid").uuid4().hex[:10])
    text: str


class AppConfig(BaseModel):
    reminders: List[ReminderMessage] = Field(default_factory=lambda: [
        ReminderMessage(id="r1", text="Drink water"),
        ReminderMessage(id="r2", text="Stretch for 2 minutes"),
    ])
    sound_enabled: bool = True
    active_gpu_threshold: int = 80
    inactive_gpu_threshold: int = 35
    inactive_hold_seconds: int = 10
    sample_interval_ms: int = 1000

    def to_monitor_config(self) -> dict:
        return {
            "active_gpu_threshold": self.active_gpu_threshold,
            "inactive_gpu_threshold": self.inactive_gpu_threshold,
            "inactive_hold_seconds": self.inactive_hold_seconds,
            "sample_interval_ms": self.sample_interval_ms,
        }
