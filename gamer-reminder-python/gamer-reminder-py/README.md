# Gamer Reminder (Windows-only, Python)

A minimal Windows desktop app that monitors configured game processes and triggers reminders when a game session ends.

## Features (v1)
- Process-based detection: track configured `*.exe` names, detect start/stop transitions
- Debounced `GAME_ENDED` event (process absent for N seconds)
- Reminders on end:
  - Windows toast notification (`win10toast`)
  - Optional sound (`winsound.Beep`)
- Simple UI (PySide6):
  - Add/remove game exe names
  - Add/remove reminder messages
  - Toggle sound
  - Start/stop monitoring
- Persistence: local JSON config in `%APPDATA%\GamerReminder\config.json`
- Basic logging: console + file (`%APPDATA%\GamerReminder\logs\app.log`)

## Repo Layout (monorepo-style)
- `apps/desktop`: Desktop UI app (PySide6)
- `packages/core`: Monitoring + reminder engine
- `packages/shared`: Types/utils and configuration model

## Prerequisites
- Windows 10/11
- Python 3.10+ (3.11 recommended)

## Install
From repo root:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run (dev)
```bash
python -m apps.desktop
```

## Notes / TODO
- CPU/GPU/resource-based detection is stubbed via `ResourceHeuristic` interface (no-op implementation included).
  Add a Windows implementation later (PerfCounters/ETW/vendor APIs).
- Process detection uses polling (`psutil`) for simplicity and reliability.
