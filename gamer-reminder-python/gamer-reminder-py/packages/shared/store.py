from __future__ import annotations

import json
from typing import Any

from packages.shared.config import AppConfig
from packages.shared.paths import config_path, ensure_app_dirs


class ConfigStore:
    def __init__(self) -> None:
        ensure_app_dirs()
        self._path = config_path()

    def load(self) -> AppConfig:
        if not self._path.exists():
            cfg = AppConfig()
            self.save(cfg)
            return cfg

        try:
            raw = self._path.read_text(encoding="utf-8")
            data: Any = json.loads(raw)
            return AppConfig.model_validate(data)
        except Exception:
            cfg = AppConfig()
            self.save(cfg)
            return cfg

    def save(self, cfg: AppConfig) -> None:
        self._path.write_text(cfg.model_dump_json(indent=2), encoding="utf-8")

    def path(self) -> str:
        return str(self._path)
