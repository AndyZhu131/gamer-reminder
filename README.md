# Gamer Reminder (Windows-only, Python)

A minimal Windows desktop app that monitors hardware utilization (GPU/CPU) to detect active gaming sessions and triggers reminders when gaming activity drops.

## Features (v2 - Hardware-based)
- Hardware-based detection: monitors GPU utilization (primary) and CPU utilization (fallback)
- State machine: IDLE → ACTIVE → SUSPECT_INACTIVE → INACTIVE
- Configurable thresholds:
  - Active GPU threshold (default: 80%)
  - Inactive GPU threshold (default: 35%)
  - Inactive hold duration (default: 10 seconds)
  - Sample interval (default: 1000ms)
- Debounced `GAME_ENDED` event (inactivity sustained for configured duration)
- Reminders on end:
  - Windows toast notification (`win10toast`)
  - Optional sound (`winsound.Beep`)
- Simple UI (PySide6):
  - Real-time GPU/CPU metrics display
  - Activity state indicator
  - Add/remove reminder messages
  - Configure hardware thresholds
  - Toggle sound
  - Start/stop monitoring
- Persistence: local JSON config in `%APPDATA%\GamerReminder\config.json`
- Basic logging: console + file (`%APPDATA%\GamerReminder\logs\app.log`)

## GPU Detection Notes
- GPU detection uses Windows Performance Counters (PDH API)
- If GPU counters are unavailable, the app automatically falls back to CPU-only mode
- GPU detection may not work on all systems; CPU fallback ensures the app remains functional

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
- GPU detection via PDH may not work on all systems. The app automatically falls back to CPU-only mode if GPU counters are unavailable.
- Future improvements could include:
  - Vendor-specific GPU APIs (NVIDIA/AMD/Intel) for more reliable GPU telemetry
  - WMI-based GPU detection as an alternative to PDH
  - Per-process GPU utilization tracking
