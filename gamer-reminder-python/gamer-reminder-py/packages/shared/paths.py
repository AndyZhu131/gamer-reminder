from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "GamerReminder"

def app_data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / APP_NAME

def config_path() -> Path:
    return app_data_dir() / "config.json"

def logs_dir() -> Path:
    return app_data_dir() / "logs"

def log_path() -> Path:
    return logs_dir() / "app.log"

def ensure_app_dirs() -> None:
    app_data_dir().mkdir(parents=True, exist_ok=True)
    logs_dir().mkdir(parents=True, exist_ok=True)
