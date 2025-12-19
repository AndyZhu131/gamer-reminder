from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from packages.shared.paths import log_path, ensure_app_dirs


def setup_logging() -> None:
    ensure_app_dirs()
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    if root.handlers:
        return

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    fh = RotatingFileHandler(str(log_path()), maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)
    root.addHandler(fh)
