"""Keep the paper account current after the Grok Bot trial ends.

Weekdays 08:30: start watcher (news is daily TW_News_0830 / TW_News_2130).
On start: catch up --live from cache if missed days (no 08:30 download).
Weekdays 09:00-13:30: intraday breakout ALERTS (no fills).
Weekdays 16:00: backup live if TW_Paper_Account stamp not today.
Weekdays 22:00: exit (scheduled stop_paper_watcher.bat is the backup).
Logs to paper/watcher.log. Not a broker.
"""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import proc_lock

ROOT = Path(__file__).resolve().parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
if not PY.exists():
    PY = Path(sys.executable)
LOG = ROOT / "paper" / "watcher.log"
LOCK = ROOT / "paper" / "watcher.lock"
TZ = ZoneInfo("Asia/Taipei")
STAMP = ROOT / "paper" / "last_live_run.txt"
ALERT_STAMP = ROOT / "paper" / "last_alert_session.txt"
NEWS_0830_STAMP = ROOT / "paper" / "last_news_0830.txt"
NEWS_2130_STAMP = ROOT / "paper" / "last_news_2130.txt"


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now(TZ):%Y-%m-%d %H:%M:%S} {msg}\n"
    for _ in range(3):
        try:
            with LOG.open("a", encoding="utf-8") as f:
                f.write(line)
            return
        except OSError:
            time.sleep(0.2)
    try:
        sys.stderr.write(line)
    except OSError:
        pass


def already_ran_today(path: Path, now: datetime) -> bool:
    if not path.exists():
        return False
    try:
        day = path.read_text(encoding="utf-8").strip()[:10]
    except OSError:
        return False
    return day == now.strftime("%Y-%m-%d")


def mark(path: Path, now: datetime) -> None:
    path.write_text(now.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")


def run_live() -> int:
    cmd = [str(PY), str(ROOT / "paper_daily.py"), "--live", "--download"]
    log("run: " + " ".join(cmd))
    p = subprocess.run(cmd, cwd=str(ROOT))
    log(f"live exit {p.returncode}")
    return p.returncode


def run_alerts() -> int:
    cmd = [str(PY), str(ROOT / "paper_alert.py")]
    log("run: " + " ".join(cmd))
    p = subprocess.run(cmd, cwd=str(ROOT))
    log(f"alert exit {p.returncode}")
    return p.returncode


def run_news(slot: str) -> int:
    cmd = [str(PY), str(ROOT / "news_risk.py"), "--slot", slot]
    log("run: " + " ".join(cmd))
    p = subprocess.run(cmd, cwd=str(ROOT))
    log(f"news {slot} exit {p.returncode}")
    return p.returncode


def past_news_2130(now: datetime) -> bool:
    if now.weekday() >= 5:
        return False
    start = now.replace(hour=21, minute=30, second=0, microsecond=0)
    return now >= start and not past_stop(now)


def past_stop(now: datetime) -> bool:
    """Weekday 22:00 or later — go to sleep until next 08:30 start."""
    if now.weekday() >= 5:
        return True
    return now.hour >= 22


def in_session(now: datetime) -> bool:
    if now.weekday() >= 5:
        return False
    start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    end = now.replace(hour=13, minute=35, second=0, microsecond=0)
    return start <= now <= end


def seconds_until_next(now: datetime) -> float:
    """Wake for 09:00 alerts or 16:00 live, whichever is next."""
    candidates: list[datetime] = []
    t = now
    for i in range(10):
        day = (t + timedelta(days=i)).replace(second=0, microsecond=0)
        if day.weekday() >= 5:
            continue
        for h, m in ((9, 0), (16, 0), (22, 0)):
            slot = day.replace(hour=h, minute=m)
            if slot > now:
                candidates.append(slot)
    if not candidates:
        return 3600.0
    return max(15.0, (min(candidates) - now).total_seconds())


def main() -> None:
    if not proc_lock.acquire(LOCK):
        log("watcher already running, exit")
        return
    log("watcher start")
    now = datetime.now(TZ)
    if past_stop(now):
        log("watcher stop (off hours; weekday 08:30–22:00)")
        return
    if not already_ran_today(STAMP, now):
        run_live()
        mark(STAMP, datetime.now(TZ))
    else:
        log("already ran live today, skip catch-up")

    while True:
        now = datetime.now(TZ)
        if past_stop(now):
            log("watcher stop (22:00)")
            return
        if in_session(now) and not already_ran_today(ALERT_STAMP, now):
            rc = run_alerts()
            if rc == 0:
                mark(ALERT_STAMP, datetime.now(TZ))
            else:
                log(f"alert failed rc={rc}, will retry")
            continue
        if now.weekday() < 5 and now.hour >= 16 and not already_ran_today(STAMP, now):
            run_live()
            mark(STAMP, now)
            continue
        wait = seconds_until_next(now)
        log(f"sleep {wait:.0f}s")
        time.sleep(min(wait, 600.0))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("watcher stop")
    except Exception as exc:  # noqa: BLE001 — stay alive note then exit
        log(f"watcher crash: {exc!r}")
        raise
