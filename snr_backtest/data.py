"""Download and cache OHLCV from yfinance. Flatten MultiIndex columns.

Cache lives under data/ as both parquet and csv so reruns do not hit the network.
If a ticker fails, log a warning and continue.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from config import DATA_DIR, END_DATE, INDEX_TICKER, TICKERS, WARMUP_START

log = logging.getLogger("trade.data")

OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def _safe_stem(ticker: str) -> str:
    return ticker.replace("^", "").replace("/", "_")


def cache_paths(ticker: str) -> tuple[Path, Path]:
    stem = _safe_stem(ticker)
    return DATA_DIR / f"{stem}.parquet", DATA_DIR / f"{stem}.csv"


def _clip_end(df: pd.DataFrame, end_date: str | None) -> pd.DataFrame:
    """Clip to a backtest sample end. Paper live passes None so new sessions keep flowing."""
    if end_date is None or df is None or df.empty:
        return df
    return df[df.index <= pd.Timestamp(end_date)]


def flatten_ohlcv(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """yfinance 1.x often returns MultiIndex columns even for a single ticker."""
    if df is None or df.empty:
        return pd.DataFrame(columns=OHLCV)

    if isinstance(df.columns, pd.MultiIndex):
        found = False
        for lvl in range(df.columns.nlevels):
            values = [str(v) for v in df.columns.get_level_values(lvl)]
            if ticker in values:
                try:
                    df = df.xs(ticker, axis=1, level=lvl, drop_level=True)
                    found = True
                    break
                except (KeyError, ValueError):
                    pass
        if not found:
            df = df.copy()
            df.columns = [str(c[0]) if isinstance(c, tuple) else str(c) for c in df.columns]

    rename = {}
    for c in df.columns:
        key = str(c).strip()
        low = key.lower().replace(" ", "")
        if low == "open":
            rename[c] = "Open"
        elif low == "high":
            rename[c] = "High"
        elif low == "low":
            rename[c] = "Low"
        elif low in ("close", "adjclose", "adj_close"):
            if low == "close" or "Close" not in rename.values():
                rename[c] = "Close"
        elif low == "volume":
            rename[c] = "Volume"
    df = df.rename(columns=rename)
    keep = [c for c in OHLCV if c in df.columns]
    df = df[keep].copy()
    for c in OHLCV:
        if c not in df.columns:
            df[c] = pd.NA
        df[c] = pd.to_numeric(df[c], errors="coerce")

    idx = pd.to_datetime(df.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("Asia/Taipei").tz_localize(None)
    df.index = idx.normalize()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df.dropna(subset=["Open", "High", "Low", "Close"], how="any")
    df = df[(df["Open"] > 0) & (df["High"] > 0) & (df["Low"] > 0) & (df["Close"] > 0)]
    return df


def _download_one(ticker: str, end_date: str | None = END_DATE) -> pd.DataFrame:
    import yfinance as yf

    # yfinance `end` is exclusive on some versions; add one day so the last
    # session of a backtest sample is kept. Paper live passes end_date=None.
    end = None
    if end_date:
        end = (pd.Timestamp(end_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    kwargs = dict(
        start=WARMUP_START,
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=False,
    )
    if end:
        kwargs["end"] = end
    df = yf.download(ticker, **kwargs)
    return _clip_end(flatten_ohlcv(df, ticker), end_date)


def save_cache(ticker: str, df: pd.DataFrame) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    pq, csv = cache_paths(ticker)
    df.to_parquet(pq)
    df.to_csv(csv, encoding="utf-8-sig", date_format="%Y-%m-%d")


def load_cache(ticker: str, end_date: str | None = END_DATE) -> pd.DataFrame | None:
    pq, csv = cache_paths(ticker)
    if pq.exists():
        df = pd.read_parquet(pq)
        df.index = pd.to_datetime(df.index).normalize()
        return _clip_end(df, end_date)
    if csv.exists():
        df = pd.read_csv(csv, index_col=0, parse_dates=True, encoding="utf-8-sig")
        df.index = pd.to_datetime(df.index).normalize()
        return _clip_end(flatten_ohlcv(df, ticker), end_date)
    return None


def get_price(
    ticker: str,
    force_download: bool = False,
    end_date: str | None = END_DATE,
) -> pd.DataFrame | None:
    if not force_download:
        cached = load_cache(ticker, end_date=end_date)
        if cached is not None and len(cached) > 0:
            log.info(
                "cache hit %s  rows=%d  %s → %s",
                ticker, len(cached), cached.index.min().date(), cached.index.max().date(),
            )
            return cached
    try:
        df = _download_one(ticker, end_date=end_date)
    except Exception as exc:  # noqa: BLE001 — network / yfinance is messy
        log.warning("download FAILED %s: %s", ticker, exc)
        return None
    if df is None or df.empty:
        log.warning("download empty %s", ticker)
        return None
    save_cache(ticker, df)
    log.info(
        "downloaded %s  rows=%d  %s → %s",
        ticker, len(df), df.index.min().date(), df.index.max().date(),
    )
    return df


def load_universe(force_download: bool = False) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Return {ticker: df} and a list of tickers that failed."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    prices: dict[str, pd.DataFrame] = {}
    failed: list[str] = []
    for ticker in list(TICKERS.keys()) + [INDEX_TICKER]:
        df = get_price(ticker, force_download=force_download)
        if df is None or df.empty:
            failed.append(ticker)
            continue
        prices[ticker] = df
    return prices, failed
