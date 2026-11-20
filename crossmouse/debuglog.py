from __future__ import annotations

import os
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path

LOG_NAME = "debug.log"
LINUX_INSTALL_ROOT = Path("/usr/lib/crossmouse")
LINUX_LOG_DIR = Path("/var/log/crossmouse")


def _default_preferred_path() -> Path:
    if getattr(sys, "frozen", False) and sys.platform == "win32":
        return Path(sys.executable).resolve().parent / LOG_NAME
    package_parent = Path(__file__).resolve().parent.parent
    if sys.platform != "win32" and package_parent == LINUX_INSTALL_ROOT:
        return LINUX_LOG_DIR / LOG_NAME
    return package_parent / LOG_NAME


def debug_log_path(preferred: Path | None = None) -> Path:
    candidates = [preferred if preferred is not None else _default_preferred_path()]
    cwd_candidate = Path.cwd() / LOG_NAME
    if cwd_candidate != candidates[0]:
        candidates.append(cwd_candidate)
    temp_candidate = Path(tempfile.gettempdir()) / LOG_NAME
    if temp_candidate not in candidates:
        candidates.append(temp_candidate)
    for candidate in candidates:
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            with candidate.open("a", encoding="utf-8"):
                pass
            return candidate
        except OSError:
            continue
    return Path(os.devnull)


class DebugLogger:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._file = path.open("a", encoding="utf-8", buffering=1)
        self._closed = False
        self._lock = threading.Lock()

    def log(self, message: str) -> None:
        with self._lock:
            if self._closed:
                return
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            self._file.write(f"{stamp} {message}\n")
            self._file.flush()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._file.close()
            self._closed = True
