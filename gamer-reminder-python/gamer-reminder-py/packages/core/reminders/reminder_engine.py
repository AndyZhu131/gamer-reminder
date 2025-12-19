from __future__ import annotations

from typing import List
from packages.shared.config import ReminderMessage


def build_reminder_payload(exe: str, reminders: List[ReminderMessage]) -> dict:
    title = "Gamer Reminder"
    if reminders:
        body_lines = ["Session ended: " + exe, "", *[f"• {r.text}" for r in reminders]]
    else:
        body_lines = ["Session ended: " + exe, "", "No reminders configured."]
    return {"title": title, "body": "\n".join(body_lines)}
