from __future__ import annotations

from typing import List
from packages.shared.config import ReminderMessage


def build_reminder_payload(reminders: List[ReminderMessage], session_name: str = "Gaming Session") -> dict:
    title = "Gamer Reminder"
    if reminders:
        body_lines = [f"Session ended: {session_name}", "", *[f"• {r.text}" for r in reminders]]
    else:
        body_lines = [f"Session ended: {session_name}", "", "No reminders configured."]
    return {"title": title, "body": "\n".join(body_lines)}
