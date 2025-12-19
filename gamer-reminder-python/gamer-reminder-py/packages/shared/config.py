from __future__ import annotations

from typing import List
from pydantic import BaseModel, Field


class ReminderMessage(BaseModel):
    id: str = Field(default_factory=lambda: "r_" + __import__("uuid").uuid4().hex[:10])
    text: str


class AppConfig(BaseModel):
    games: List[str] = Field(default_factory=lambda: ["eldenring.exe"])
    reminders: List[ReminderMessage] = Field(default_factory=lambda: [
        ReminderMessage(id="r1", text="Drink water"),
        ReminderMessage(id="r2", text="Stretch for 2 minutes"),
    ])
    sound_enabled: bool = True
    poll_interval_ms: int = 1500
    end_debounce_ms: int = 8000

    def to_monitor_config(self) -> dict:
        return {
            "tracked_exe_names": self.games,
            "poll_interval_ms": self.poll_interval_ms,
            "end_debounce_ms": self.end_debounce_ms,
        }
