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
- GPU detection uses NVIDIA `nvidia-smi` CLI (NVIDIA GPUs only)
- If `nvidia-smi` is unavailable or fails, the app automatically falls back to CPU-only mode
- GPU availability is checked at runtime (not init-time), allowing automatic recovery if GPU becomes available
- The app retries GPU detection every 10 seconds while monitoring if GPU was previously unavailable
- CPU fallback ensures the app remains functional on systems without NVIDIA GPUs or when `nvidia-smi` is unavailable

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
- GPU detection requires NVIDIA GPU with `nvidia-smi` CLI available. The app automatically falls back to CPU-only mode if unavailable.
- Future improvements could include:
  - AMD GPU support (via `rocm-smi` or similar)
  - Intel GPU support (via `intel_gpu_top` or similar)
  - Per-process GPU utilization tracking
