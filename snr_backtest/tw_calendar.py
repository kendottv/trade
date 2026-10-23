"""TWSE trading calendar: weekends + official holidays + ad-hoc closures.

Ad-hoc closures (typhoon etc.): add lines "YYYY-MM-DD" (optional "# note")
to paper/extra_holidays.txt; read at runtime.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXTRA_FILE = ROOT / "paper" / "extra_holidays.txt"

# Source: TWSE 115年市場開休市日期 (holidaySchedule, queryYear=2026)
# Includes 2/12-2/13 (no trading, settlement only).
TWSE_HOLIDAYS: set[str] = {
    "2026-01-01", "2026-02-12", "2026-02-13", "2026-02-16", "2026-02-17",
    "2026-02-18", "2026-02-19", "2026-02-20", "2026-02-27", "2026-04-03",
    "2026-04-06", "2026-05-01", "2026-06-19", "2026-09-25", "2026-09-28",
    "2026-10-09", "2026-10-26", "2026-12-25",
    # ad-hoc: typhoon full-day closure (TWSE notice 2026-10-22)
    "2026-10-23",
}


def _to_date(d) -> date:
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    if hasattr(d, "date") and callable(d.date):  # pandas Timestamp
        return d.date()
    return date.fromisoformat(str(d)[:10])


def extra_holidays() -> set[str]:
    out: set[str] = set()
    try:
        for line in EXTRA_FILE.read_text(encoding="utf-8").splitlines():
            s = line.split("#", 1)[0].strip()
            if len(s) >= 10:
                out.add(s[:10])
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return out


def is_trading_day(d=None) -> bool:
    d = _to_date(d or date.today())
    if d.weekday() >= 5:
        return False
    k = d.isoformat()
    return k not in TWSE_HOLIDAYS and k not in extra_holidays()