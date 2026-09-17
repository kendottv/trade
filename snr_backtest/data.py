"""OHLCV cache.

Live paper overlays recent daily bars from 永豐 Shioaji (simulation quotes).
Long history still comes from Yahoo once, then Shioaji patches new sessions.
If cache does not cover end_date, get_price auto-downloads from Yahoo (server-safe).
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from config import DATA_DIR, END_DATE, INDEX_TICKER, TICKERS, WARMUP_START

log = logging.getLogger("trade.data")

OHLCV = ["Open", "High", "Low", "Close", "Volume"]
_SJ_DQ: dict[date, tuple[float, dict[str, tuple]]] = {}


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
    try:
        from quotes import _yf_silent

        with _yf_silent():
            df = yf.download(ticker, **kwargs)
    except Exception:
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


def _upsert_bar(df: pd.DataFrame | None, day, open_, high, low, close, volume=0.0) -> pd.DataFrame:
    ts = pd.Timestamp(day).normalize()
    row = {
        "Open": float(open_),
        "High": float(high),
        "Low": float(low),
        "Close": float(close),
        "Volume": float(volume or 0),
    }
    if df is None or df.empty:
        out = pd.DataFrame([row], index=[ts])
    else:
        out = df.copy()
        out.index = pd.to_datetime(out.index).normalize()
        for col in OHLCV:
            if col not in out.columns:
                out[col] = pd.NA
        out.loc[ts, list(row.keys())] = list(row.values())
        out = out.sort_index()
        out = out[~out.index.duplicated(keep="last")]
    return out


def _ticker_code(ticker: str) -> str:
    t = str(ticker).upper()
    if t in ("^TWII", "TWII", "IX0001", "TSE001"):
        return "IX0001"
    return t.split(".")[0]


def overlay_shioaji(tickers: list[str], lookback_days: int = 10) -> dict[str, pd.DataFrame]:
    """Patch recent completed sessions onto cache from Shioaji. No orders.

    Before 15:00 do not write *today* (intraday 1m is not the official close).
    """
    from quotes import INDEX_YAHOO, get_feed, now_taipei

    feed = get_feed()
    if getattr(feed, "name", "") != "shioaji" or not hasattr(feed.impl, "api"):
        return {}
    api = feed.impl.api
    now = now_taipei()
    today = now.date()
    days: list[date] = []
    d = today
    while len(days) < lookback_days:
        if d.weekday() < 5:
            if d < today or now.hour >= 15:
                days.append(d)
        d -= timedelta(days=1)
        if (today - d).days > 21:
            break
    wanted = {str(t): _ticker_code(t) for t in tickers if t}
    by_code: dict[str, str] = {}
    for t, c in wanted.items():
        by_code.setdefault(c, t)
    patched: dict[str, pd.DataFrame] = {}

    quotes_by_day: dict[date, dict[str, tuple]] = {}
    now_ts = time.time()
    for day in days:
        hit = _SJ_DQ.get(day)
        if hit and now_ts - hit[0] < 300:
            quotes_by_day[day] = hit[1]
            continue
        try:
            dq = api.daily_quotes(date=day)
        except Exception as exc:
            log.warning("shioaji daily_quotes %s: %s", day, exc)
            continue
        n = len(getattr(dq, "Code", []) or [])
        if n <= 0:
            continue
        codes = list(dq.Code)
        table: dict[str, tuple] = {}
        for i, code in enumerate(codes):
            c = str(code)
            try:
                table[c] = (
                    float(dq.Open[i]),
                    float(dq.High[i]),
                    float(dq.Low[i]),
                    float(dq.Close[i]),
                    float(dq.Volume[i] if getattr(dq, "Volume", None) is not None else 0),
                )
            except (TypeError, ValueError, IndexError):
                continue
        _SJ_DQ[day] = (now_ts, table)
        quotes_by_day[day] = table

    for ticker, code in wanted.items():
        cached = load_cache(ticker, end_date=None)
        df = cached
        changed = False
        if code == "IX0001" or ticker in (INDEX_YAHOO, "^TWII", INDEX_TICKER):
            start = (min(days) if days else today).isoformat()
            end = (max(days) if days else today).isoformat()
            try:
                contract = feed.impl.contract(INDEX_YAHOO)
                kb = api.kbars(contract, start=start, end=end) if contract is not None else None
            except Exception as exc:
                log.warning("shioaji kbars TWII: %s", exc)
                kb = None
            if kb is not None and getattr(kb, "Close", None):
                kdf = pd.DataFrame(
                    {
                        "Open": kb.Open,
                        "High": kb.High,
                        "Low": kb.Low,
                        "Close": kb.Close,
                        "Volume": getattr(kb, "Volume", [0] * len(kb.Close)),
                    },
                    index=pd.to_datetime(kb.ts),
                )
                kdf.index = pd.to_datetime(kdf.index).tz_localize(None)
                daily = kdf.resample("1D").agg(
                    {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
                ).dropna(how="any")
                for ts, row in daily.iterrows():
                    dd = pd.Timestamp(ts).date()
                    if dd not in days:
                        continue
                    df = _upsert_bar(df, ts, row["Open"], row["High"], row["Low"], row["Close"], row["Volume"])
                    changed = True
        else:
            for day, table in quotes_by_day.items():
                bar = table.get(code)
                if not bar:
                    continue
                df = _upsert_bar(df, day, *bar)
                changed = True
        if changed and df is not None and not df.empty:
            save_cache(ticker, df)
            patched[ticker] = df
            log.info(
                "shioaji overlay %s rows=%d last=%s",
                ticker, len(df), df.index.max().date(),
            )
    return patched



def _cache_covers(df: pd.DataFrame | None, end_date: str | None) -> bool:
    """True if cached bars already reach the requested sample end (or ~yesterday for live)."""
    if df is None or df.empty:
        return False
    last = pd.Timestamp(df.index.max()).normalize()
    if end_date is None:
        # live/paper: treat cache as fresh if last bar is yesterday or today
        floor = pd.Timestamp.now().normalize() - pd.Timedelta(days=1)
        return last >= floor
    return last >= pd.Timestamp(end_date).normalize()

def get_price(
    ticker: str,
    force_download: bool = False,
    end_date: str | None = END_DATE,
    cache_only: bool = False,
) -> pd.DataFrame | None:
    """Load OHLCV. Auto-downloads from Yahoo when cache does not cover end_date.

    end_date=None means live/paper (through latest available). Backtests pass an
    explicit end; if the local parquet stops earlier, we refresh without needing
    paper_watcher — so a server-side backtest can stay current.
    """
    paper = end_date is None
    # Judge coverage on the *full* cache, then clip for the caller.
    cached_full = load_cache(ticker, end_date=None)
    if paper and force_download:
        try:
            overlay_shioaji([ticker])
            cached_full = load_cache(ticker, end_date=None)
        except Exception as exc:
            log.warning("shioaji overlay skip %s: %s", ticker, exc)
        if cached_full is not None and len(cached_full) > 0 and _cache_covers(cached_full, None):
            return cached_full

    if cache_only:
        need = False
    else:
        need = force_download or not _cache_covers(cached_full, end_date)
    if not need:
        out = cached_full if paper else _clip_end(cached_full, end_date)
        log.info(
            "cache hit %s  rows=%d  %s → %s",
            ticker,
            len(out) if out is not None else 0,
            out.index.min().date() if out is not None and len(out) else "?",
            out.index.max().date() if out is not None and len(out) else "?",
        )
        return out

    try:
        df = _download_one(ticker, end_date=end_date)
    except Exception as exc:  # noqa: BLE001 — network / yfinance is messy
        log.warning("download FAILED %s: %s", ticker, exc)
        if cached_full is None or cached_full.empty:
            return None
        return cached_full if paper else _clip_end(cached_full, end_date)
    if df is None or df.empty:
        log.warning("download empty %s", ticker)
        if cached_full is None or cached_full.empty:
            return None
        return cached_full if paper else _clip_end(cached_full, end_date)

    # Merge with any longer existing cache so a shorter clip download cannot wipe history.
    if cached_full is not None and not cached_full.empty:
        both = pd.concat([cached_full, df])
        both = both[~both.index.duplicated(keep="last")].sort_index()
        df = both
    save_cache(ticker, df)
    if paper:
        try:
            overlay_shioaji([ticker])
            again = load_cache(ticker, end_date=None)
            if again is not None and not again.empty:
                df = again
        except Exception:
            pass
    log.info(
        "downloaded %s  rows=%d  %s → %s",
        ticker, len(df), df.index.min().date(), df.index.max().date(),
    )
    return df if paper else _clip_end(df, end_date)


def load_universe(
    force_download: bool = False,
    end_date: str | None = END_DATE,
    cache_only: bool = False,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Return {ticker: df} and a list of tickers that failed.

    end_date is forwarded to get_price so backtests/servers can refresh past
    config.END_DATE when the sample window moves forward.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    prices: dict[str, pd.DataFrame] = {}
    failed: list[str] = []
    for ticker in list(TICKERS.keys()) + [INDEX_TICKER]:
        df = get_price(
            ticker,
            force_download=force_download,
            end_date=end_date,
            cache_only=cache_only,
        )
        if df is None or df.empty:
            failed.append(ticker)
            continue
        prices[ticker] = df
    return prices, failed
