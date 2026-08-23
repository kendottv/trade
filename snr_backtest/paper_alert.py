"""Intraday breakout ALERTS only. Does not trade.

During TW cash session (09:00-13:30 Asia/Taipei), poll last prices.
If last (or today's 1m high) > prior 20-day high, alarm once per ticker
per day (beep + Windows toast). After a split/減資, the 20-day high is
taken only from bars after the gap. Close confirmation + next-open fill
still happens in paper_daily.py after the close.
"""
from __future__ import annotations

import csv
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from signals import LOOKBACK, add_signal_columns
from universe import candidate_tickers, display_name, load_prices, screen_universe

TZ = ZoneInfo("Asia/Taipei")
PAPER = ROOT / "paper"
ALERT_CSV = PAPER / "alerts.csv"
ALERT_MD = PAPER / "alerts_today.md"
FIRED = PAPER / "alerts_fired.txt"
LOG = PAPER / "watcher.log"
POLL_SEC = 90
SESSION_START = (9, 0)
SESSION_END = (13, 35)
# Wider than TW 10% limit — catches 分割／減資, not 漲停.
SPLIT_GAP = 0.22


def log(msg: str) -> None:
    PAPER.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now(TZ):%Y-%m-%d %H:%M:%S} {msg}\n"
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line)


def in_session(now: datetime) -> bool:
    if now.weekday() >= 5:
        return False
    start = now.replace(hour=SESSION_START[0], minute=SESSION_START[1], second=0, microsecond=0)
    end = now.replace(hour=SESSION_END[0], minute=SESSION_END[1], second=0, microsecond=0)
    return start <= now <= end


NOTIFY_PS1 = ROOT / "notify_alert.ps1"


def play_alarm() -> None:
    """PC speaker / default device beeps. Runs in a thread so toast can show now."""

    def _run() -> None:
        try:
            import winsound

            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            for _ in range(3):
                winsound.Beep(880, 180)
                winsound.Beep(1320, 320)
        except Exception as e:  # noqa: BLE001 — never kill the alert loop
            log(f"alarm sound fail: {e}")

    threading.Thread(target=_run, daemon=True).start()


def show_toast(title: str, body: str) -> bool:
    """Windows notification center toast. Returns False if PowerShell fails."""
    if not NOTIFY_PS1.exists():
        log("notify_alert.ps1 missing")
        return False
    try:
        p = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-WindowStyle", "Hidden",
                "-ExecutionPolicy", "Bypass",
                "-File", str(NOTIFY_PS1),
                "-Title", title,
                "-Body", body,
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=20,
        )
        if p.returncode != 0:
            err = (p.stderr or p.stdout or "").strip()[:300]
            log(f"toast fail rc={p.returncode} {err}")
            return False
        return True
    except (OSError, subprocess.TimeoutExpired) as e:
        log(f"toast fail: {e}")
        return False


def show_popup(title: str, body: str, timeout: int = 30) -> None:
    """Fallback dialog if toast is blocked. Non-blocking; auto-closes."""
    t = title.replace('"', "'")
    b = body.replace('"', "'").replace("\n", " ")
    ps = (
        "$s = New-Object -ComObject WScript.Shell; "
        f'$s.Popup("{b}", {int(timeout)}, "{t}", 48)'
    )
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
            cwd=str(ROOT),
        )
    except OSError as e:
        log(f"popup fail: {e}")


def notify(title: str, body: str) -> None:
    """Sound + Windows toast. Popup only if toast fails."""
    log(f"alarm: {body}")
    play_alarm()
    if not show_toast(title, body):
        show_popup(title, body, timeout=30)


def load_fired(day: str) -> set[str]:
    if not FIRED.exists():
        return set()
    out: set[str] = set()
    for line in FIRED.read_text(encoding="utf-8").splitlines():
        if line.startswith(day + "\t"):
            out.add(line.split("\t", 1)[1].strip())
    return out


def mark_fired(day: str, ticker: str) -> None:
    with FIRED.open("a", encoding="utf-8") as f:
        f.write(f"{day}\t{ticker}\n")


def append_csv(row: dict) -> None:
    new = not ALERT_CSV.exists()
    with ALERT_CSV.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["time", "ticker", "name", "last", "prior_high_20", "note"])
        if new:
            w.writeheader()
        w.writerow(row)


def write_md(day: str, rows: list[str]) -> None:
    body = f"# 盤中預警 {day}\n\n尚未收盤確認，不會進場。\n\n"
    body += "\n".join(rows) if rows else "（目前沒有破高點）\n"
    ALERT_MD.write_text(body, encoding="utf-8")


def last_price(ticker: str) -> float | None:
    try:
        from quotes import get_feed

        q = get_feed().last(ticker)
        if q is not None and q.last > 0:
            return float(q.last)
    except Exception as e:
        log(f"last_price {ticker} fail: {e}")
    return None


def live_print(ticker: str, lvl: float) -> tuple[float | None, str]:
    """Last price, then today's 1m high if last is still stuck at the 20-day high.

    Consecutive 漲停 + delayed Yahoo last often equals yesterday's close, which
    is already the 20-day high — 1m high is the only way to see today's limit.
    """
    last = last_price(ticker)
    if last is not None and last > lvl:
        return last, "last"
    try:
        from quotes import get_feed

        bar = get_feed().session_bar(ticker)
        if bar and bar.get("High") and float(bar["High"]) > 0:
            hi = float(bar["High"])
            px = max(last or 0.0, hi)
            if px > lvl:
                return px, "1m_high"
            if last is not None:
                return last, "last"
            return hi, "1m_high"
    except Exception as e:
        log(f"live_print {ticker} fail: {e}")
    return last, "last"


def lookback_high(hist: pd.DataFrame, n: int = LOOKBACK) -> float | None:
    """Max of the last n completed highs. If a split-like gap sits in the
    window, only use bars after that gap (so 分割前 200 元不會擋住現在 26 元).
    """
    if hist is None or hist.empty or "High" not in hist.columns:
        return None
    h = hist.copy()
    h.index = pd.to_datetime(h.index).normalize()
    h = h[~h.index.duplicated(keep="last")].sort_index()
    window = h.tail(max(int(n) * 2, 40))
    if "Close" in window.columns and len(window) >= 3:
        close = window["Close"].astype(float)
        gap = (close / close.shift(1) - 1.0).abs()
        splits = gap[gap > SPLIT_GAP]
        if len(splits):
            after = splits.index[-1]
            post = h[h.index > after]
            if len(post) >= 2:
                window = post
    highs = window["High"].astype(float).tail(int(n))
    if highs.empty:
        return None
    lvl = float(highs.max())
    return lvl if lvl > 0 else None


def build_levels() -> dict[str, float]:
    names = candidate_tickers()
    prices, _failed = load_prices(list(names) + ["^TWII"], force_download=False)
    twii = prices.get("^TWII")
    if twii is not None and len(twii):
        asof = pd.Timestamp(twii.index.max()).normalize()
    else:
        asof = pd.Timestamp(datetime.now(TZ).date())
    passed, _table = screen_universe(prices, names, asof)
    levels: dict[str, float] = {}
    for ticker in passed:
        df = prices.get(ticker)
        if df is None or df.empty:
            continue
        hist = df[df.index <= asof]
        if hist.empty or "High" not in hist.columns:
            continue
        lvl = lookback_high(hist, LOOKBACK)
        if lvl is not None:
            levels[ticker] = lvl
    return levels


def scan_once(levels: dict[str, float], names: dict[str, str], fired: set[str], md_rows: list[str]) -> None:
    now = datetime.now(TZ)
    day = now.strftime("%Y-%m-%d")
    for ticker, lvl in levels.items():
        if ticker in fired:
            continue
        last, src = live_print(ticker, lvl)
        if last is None or last <= lvl:
            continue
        name = display_name(ticker, names)
        src_bit = "；盤中1分K" if src == "1m_high" else ""
        note = (
            f"{name} 盤中 {last:.2f} 破 20日高 {lvl:.2f}"
            f"（預警未進場；Yahoo 報價可能延遲{src_bit}）"
        )
        log(note)
        append_csv({
            "time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "ticker": ticker,
            "name": name,
            "last": f"{last:.4f}",
            "prior_high_20": f"{lvl:.4f}",
            "note": "intraday_alert_no_fill",
        })
        line = f"- {now:%H:%M} {name} ({ticker}) 現價 {last:.2f} > {lvl:.2f}"
        md_rows.append(line)
        write_md(day, md_rows)
        notify("紙上帳戶預警", note)
        mark_fired(day, ticker)
        fired.add(ticker)


def run_session() -> None:
    PAPER.mkdir(parents=True, exist_ok=True)
    now = datetime.now(TZ)
    day = now.strftime("%Y-%m-%d")
    log("alert session start")
    names = candidate_tickers()
    try:
        levels = build_levels()
    except Exception as e:
        log(f"build_levels fail: {e}")
        raise SystemExit(1) from e
    if not levels:
        log("build_levels empty")
        raise SystemExit(1)
    log(f"watching {len(levels)} names")
    fired = load_fired(day)
    md_rows: list[str] = []
    write_md(day, md_rows)
    while in_session(datetime.now(TZ)):
        try:
            scan_once(levels, names, fired, md_rows)
        except Exception as e:
            log(f"scan fail: {e}")
        time.sleep(POLL_SEC)
    log("alert session end")


def seconds_until_session(now: datetime) -> float:
    if in_session(now):
        return 0.0
    t = now
    for _ in range(8):
        start = t.replace(hour=9, minute=0, second=0, microsecond=0)
        if t.weekday() < 5 and t < start:
            return max(15.0, (start - now).total_seconds())
        t = (t + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        while t.weekday() >= 5:
            t += timedelta(days=1)
        start = t.replace(hour=9, minute=0, second=0, microsecond=0)
        return max(15.0, (start - now).total_seconds())
    return 3600.0


if __name__ == "__main__":
    if "--test" in sys.argv:
        notify(
            "紙上帳戶預警（測試）",
            "這是測試：你應該聽到提示音，並在右下角看到 Windows 通知。不成交。",
        )
        time.sleep(4)
    else:
        run_session()
