from __future__ import annotations

import psutil


def running_exe_names_lower() -> set[str]:
    names: set[str] = set()
    for p in psutil.process_iter(attrs=["name"]):
        try:
            n = p.info.get("name")
            if n:
                names.add(str(n).lower())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return names
