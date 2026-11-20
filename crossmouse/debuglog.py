from __future__ import annotations

import sys
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
    target = preferred if preferred is not None else _default_preferred_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8"):
            pass
        return target
    except OSError:
        return Path.cwd() / LOG_NAME


class DebugLogger:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._file = path.open("a", encoding="utf-8", buffering=1)
        self._closed = False

    def log(self, message: str) -> None:
        if self._closed:
            return
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self._file.write(f"{stamp} {message}\n")
        self._file.flush()

    def close(self) -> None:
        if self._closed:
            return
        self._file.close()
        self._closed = True
