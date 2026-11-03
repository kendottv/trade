"""One live process per lock file. Not a broker."""
from __future__ import annotations

import atexit
import ctypes
import os
import time
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
    """Return False if another live process owns the lock.
    Atomic create with O_CREAT|O_EXCL. Clears stale locks from dead PIDs.
    Empty/unparseable content with mtime < 30s is treated as in-use.
    """
    lock.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(lock), flags)
    except FileExistsError:
        try:
            raw = lock.read_text(encoding="utf-8").strip()
            old = int(raw.split()[0]) if raw else 0
        except (OSError, ValueError):
            old = 0
        if old and old != os.getpid() and pid_alive(old):
            return False
        # empty / unparseable and very recent → still being written
        if old == 0:
            try:
                age = time.time() - lock.stat().st_mtime
            except OSError:
                age = 999
            if age < 30:
                return False
        # stale lock from dead PID — remove and retry once
        try:
            lock.unlink()
        except OSError:
            return False
        try:
            fd = os.open(str(lock), flags)
        except FileExistsError:
            return False
    try:
        os.write(fd, str(os.getpid()).encode())
    finally:
        os.close(fd)

    def _clear() -> None:
        try:
            if lock.exists() and lock.read_text(encoding="utf-8").strip().startswith(str(os.getpid())):
                lock.unlink()
        except OSError:
            pass

    atexit.register(_clear)
    return True