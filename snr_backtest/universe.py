"""Liquid Taiwan universe for paper trading.

Hardcoded large/mid names (original 10 + extra liquid .TW). No live scrape.
Liquidity is screened from cached OHLCV; download failures are skipped.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from config import DATA_DIR, INDEX_NAME, INDEX_TICKER, TICKERS as ORIGINAL_TICKERS
from data import get_price, load_cache

log = logging.getLogger("trade.universe")

# Extra liquid names (TW50 / large+mid style). Skip if download fails.
EXTRA_TICKERS: dict[str, str] = {
    "2317.TW": "鴻海",
    "2454.TW": "聯發科",
    "2308.TW": "台達電",
    "2303.TW": "聯電",
    "2382.TW": "廣達",
    "2412.TW": "中華電",
    "3711.TW": "日月光投控",
    "3008.TW": "大立光",
    "2395.TW": "研華",
    "2357.TW": "華碩",
    "3231.TW": "緯創",
    "2345.TW": "智邦",
    "6669.TW": "緯穎",
    "2379.TW": "瑞昱",
    "3034.TW": "聯詠",
    "2301.TW": "光寶科",
}

# 金控／銀行：監測與新倉都不看。舊倉仍用 TP/SL，不從這裡強制平倉。
BANK_TICKERS: dict[str, str] = {
    "2881.TW": "富邦金",
    "2882.TW": "國泰金",
    "2891.TW": "中信金",
    "2886.TW": "兆豐金",
}

MIN_BARS = 80
MIN_CLOSE = 10.0
MIN_AVG_TURNOVER = 50_000_000.0  # NT$ per day, last 20 sessions
TURNOVER_WINDOW = 20


def _drop_banks(names: dict[str, str]) -> dict[str, str]:
    return {t: n for t, n in names.items() if t not in BANK_TICKERS}


def default_catalog() -> dict[str, str]:
    """Built-in names, no banks. Dashboard watchlist can narrow or extend this."""
    ordered: dict[str, str] = {}
    for t, n in ORIGINAL_TICKERS.items():
        ordered[t] = n
    for t, n in EXTRA_TICKERS.items():
        if t not in ordered:
            ordered[t] = n
    return _drop_banks(ordered)


def catalog_without_banks() -> dict[str, str]:
    return default_catalog()


def candidate_tickers() -> dict[str, str]:
    """Watchlist from the dashboard if saved, else the built-in catalog.

    Banks are always stripped so alerts and new entries never see them.
    """
    try:
        from ui_settings import load_watchlist

        watch = load_watchlist()
    except Exception:
        watch = None
    if watch:
        return _drop_banks(dict(watch))
    return default_catalog()


def display_name(ticker: str, names: dict[str, str] | None = None) -> str:
    if ticker == INDEX_TICKER:
        return INDEX_NAME
    names = names or candidate_tickers()
    if ticker in names:
        return names[ticker]
    return default_catalog().get(ticker) or BANK_TICKERS.get(ticker, ticker)


def load_prices(
    tickers: list[str],
    force_download: bool = False,
    end_date: str | None = None,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Load OHLCV via data.py cache; download missing; skip failures.

    Paper live/alert pass end_date=None so bars after the backtest sample
    (config.END_DATE) still arrive. Backtests should keep using data.get_price
    / load_universe, which default to END_DATE.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    prices: dict[str, pd.DataFrame] = {}
    failed: list[str] = []
    for ticker in tickers:
        df = None
        if not force_download:
            df = load_cache(ticker, end_date=end_date)
        if df is None or df.empty:
            try:
                df = get_price(
                    ticker,
                    force_download=force_download or df is None,
                    end_date=end_date,
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("skip %s: %s", ticker, exc)
                df = None
        if df is None or df.empty:
            failed.append(ticker)
            continue
        df = df.copy()
        df.index = pd.to_datetime(df.index).normalize()
        df = df[~df.index.duplicated(keep="last")].sort_index()
        prices[ticker] = df
        log.info(
            "loaded %s rows=%d %s → %s",
            ticker,
            len(df),
            df.index.min().date(),
            df.index.max().date(),
        )
    return prices, failed


def session_dates(
    prices: dict[str, pd.DataFrame],
    start: str | None = None,
    end: str | None = None,
) -> pd.DatetimeIndex:
    """Master calendar: union of ^TWII and 2330.TW (Yahoo often lags one)."""
    idx = None
    for key in (INDEX_TICKER, "2330.TW"):
        df = prices.get(key)
        if df is None or not len(df):
            continue
        part = pd.DatetimeIndex(pd.to_datetime(df.index).normalize())
        idx = part if idx is None else idx.union(part)
    if idx is None:
        parts = [df.index for df in prices.values() if df is not None and len(df)]
        if not parts:
            return pd.DatetimeIndex([])
        idx = parts[0]
        for p in parts[1:]:
            idx = idx.union(p)
        idx = idx.sort_values()
    idx = pd.DatetimeIndex(pd.to_datetime(idx).normalize()).unique().sort_values()
    if start:
        idx = idx[idx >= pd.Timestamp(start)]
    if end:
        idx = idx[idx <= pd.Timestamp(end)]
    return idx


def liquidity_ok(df: pd.DataFrame, asof: pd.Timestamp) -> tuple[bool, dict]:
    """Screen using bars through asof only (no look-ahead)."""
    asof = pd.Timestamp(asof).normalize()
    hist = df[df.index <= asof]
    info = {
        "bars": int(len(hist)),
        "last_close": None,
        "avg_turnover_20": None,
        "reason": "",
    }
    if len(hist) < MIN_BARS:
        info["reason"] = f"bars<{MIN_BARS}"
        return False, info
    last = hist.iloc[-1]
    close = float(last["Close"])
    info["last_close"] = close
    if close < MIN_CLOSE:
        info["reason"] = f"close<{MIN_CLOSE}"
        return False, info
    window = hist.tail(TURNOVER_WINDOW)
    if len(window) < TURNOVER_WINDOW:
        info["reason"] = "turnover_window_short"
        return False, info
    turnover = (window["Close"] * window["Volume"]).astype(float)
    avg_t = float(turnover.mean())
    info["avg_turnover_20"] = avg_t
    if avg_t < MIN_AVG_TURNOVER:
        info["reason"] = f"turnover<{MIN_AVG_TURNOVER:.0f}"
        return False, info
    info["reason"] = "ok"
    return True, info


def screen_universe(
    prices: dict[str, pd.DataFrame],
    names: dict[str, str],
    asof: pd.Timestamp,
    skip: set[str] | None = None,
) -> tuple[list[str], pd.DataFrame]:
    """Return tickers that pass liquidity at asof, plus a detail table."""
    skip = skip or {INDEX_TICKER}
    rows = []
    passed: list[str] = []
    for ticker, name in names.items():
        if ticker in skip:
            continue
        df = prices.get(ticker)
        if df is None or df.empty:
            rows.append(
                {
                    "ticker": ticker,
                    "name": name,
                    "passed": 0,
                    "bars": 0,
                    "last_close": "",
                    "avg_turnover_20": "",
                    "reason": "no_data",
                }
            )
            continue
        ok, info = liquidity_ok(df, asof)
        rows.append(
            {
                "ticker": ticker,
                "name": name,
                "passed": int(ok),
                "bars": info["bars"],
                "last_close": ("" if info["last_close"] is None else round(info["last_close"], 4)),
                "avg_turnover_20": (
                    "" if info["avg_turnover_20"] is None else round(info["avg_turnover_20"], 2)
                ),
                "reason": info["reason"],
            }
        )
        if ok:
            passed.append(ticker)
    table = pd.DataFrame(rows)
    return passed, table


def save_universe_csv(table: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(path, index=False, encoding="utf-8-sig")
