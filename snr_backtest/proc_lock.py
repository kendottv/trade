"""One live process per lock file. Not a broker."""
from __future__ import annotations

import atexit
import ctypes
import os
from pathlib import Path

_SYNCHRONIZE = 0x00100000
_kernel32 = ctypes.windll.kernel32


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    handle = _kernel32.OpenProcess(_SYNCHRONIZE, False, int(pid))
    if handle:
        _kernel32.CloseHandle(handle)
        return True
    return False


def acquire(lock: Path) -> bool:
    """Return False if another live process owns the lock."""
    lock.parent.mkdir(parents=True, exist_ok=True)
    if lock.exists():
        try:
            old = int(lock.read_text(encoding="utf-8").strip().split()[0])
        except (OSError, ValueError):
            old = 0
        if old and old != os.getpid() and pid_alive(old):
            return False
    lock.write_text(str(os.getpid()), encoding="utf-8")

    def _clear() -> None:
        try:
            if lock.exists() and lock.read_text(encoding="utf-8").strip().startswith(str(os.getpid())):
                lock.unlink()
        except OSError:
            pass

    atexit.register(_clear)
    return True
