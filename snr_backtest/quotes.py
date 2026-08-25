"""Live quotes for the dashboard (and later, alerts).

This is the plug-in point for 永豐 Shioaji. It NEVER places orders.

Backends
  yahoo   default now. TWII 1-minute bars. Yahoo is delayed ~15 minutes.
  shioaji later. Fill paper/broker_secrets.json, set quote.backend, then
          implement ShioajiFeed.connect(). Still quotes only.

Paper fills stay t close / t+1 open in paper_daily.py.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parent
PAPER = ROOT / "paper"
SECRETS_PATH = PAPER / "broker_secrets.json"
TZ = ZoneInfo("Asia/Taipei")
INDEX_YAHOO = "^TWII"
INDEX_SHIOAJI = "TSE001"

SESSION_START = (9, 0)
SESSION_END = (13, 30)
POLL_SEC = 15

_YF_QUIET = False


def _quiet_yfinance() -> None:
    """Yahoo often prints 'possibly delisted' when a fetch is empty. Not true."""
    global _YF_QUIET
    if _YF_QUIET:
        return
    _YF_QUIET = True
    import logging
    import warnings

    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    logging.getLogger("yfinance.scrapers").setLevel(logging.CRITICAL)
    warnings.filterwarnings("ignore", message=".*possibly delisted.*")
    warnings.filterwarnings("ignore", message=".*no price data found.*")


@contextlib.contextmanager
def _yf_silent():
    _quiet_yfinance()
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        yield


@dataclass(frozen=True)
class Quote:
    ticker: str
    last: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    prev_close: float | None = None
    ts: datetime | None = None
    source: str = "yahoo"
    delayed: bool = True


class NotConfigured(RuntimeError):
    """Backend selected but credentials / package missing. Do not login here."""


def now_taipei() -> datetime:
    return datetime.now(TZ)


def in_cash_session(now: datetime | None = None) -> bool:
    now = now or now_taipei()
    if now.weekday() >= 5:
        return False
    start = now.replace(hour=SESSION_START[0], minute=SESSION_START[1], second=0, microsecond=0)
    end = now.replace(hour=SESSION_END[0], minute=SESSION_END[1], second=0, microsecond=0)
    return start <= now <= end


def _backend_name() -> str:
    env = (os.environ.get("QUOTE_BACKEND") or "").strip().lower()
    if env:
        return env
    try:
        from ui_settings import load_raw

        raw = (load_raw().get("quote") or {}).get("backend")
        if raw:
            return str(raw).strip().lower()
    except Exception:
        pass
    if SECRETS_PATH.exists():
        try:
            data = json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
            b = str(data.get("backend") or "").strip().lower()
            if b:
                return b
        except (OSError, json.JSONDecodeError):
            pass
    return "yahoo"


def load_secrets() -> dict:
    if not SECRETS_PATH.exists():
        return {}
    try:
        data = json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _to_taipei_naive(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    idx = pd.to_datetime(idx)
    if getattr(idx, "tz", None) is not None:
        return idx.tz_convert(TZ).tz_localize(None)
    return idx


_cache: dict[str, tuple[float, object]] = {}


def _cached(key: str, ttl: float, fn):
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    val = fn()
    _cache[key] = (now, val)
    return val


class YahooFeed:
    """Current live source. Delayed. No account."""

    name = "yahoo"
    label = "Yahoo（約延遲 15 分）"
    delayed = True

    def last(self, ticker: str) -> Quote | None:
        ticker = ticker or INDEX_YAHOO

        def _pull() -> Quote | None:
            try:
                import yfinance as yf

                last = None
                prev = None
                o = h = l = None
                ts = None
                hist = None
                with _yf_silent():
                    t = yf.Ticker(ticker)
                    fi = getattr(t, "fast_info", None)
                    if fi is not None:
                        def _get(obj, *keys):
                            for k in keys:
                                try:
                                    v = obj[k] if not isinstance(obj, dict) else obj.get(k)
                                except Exception:
                                    v = getattr(obj, k, None) if not isinstance(obj, dict) else None
                                if v is not None:
                                    try:
                                        f = float(v)
                                    except (TypeError, ValueError):
                                        continue
                                    if f > 0:
                                        return f
                            return None

                        last = _get(fi, "lastPrice", "last_price", "regularMarketPrice")
                        prev = _get(fi, "previousClose", "previous_close")
                        o = _get(fi, "open", "regularMarketOpen")
                        h = _get(fi, "dayHigh", "day_high")
                        l = _get(fi, "dayLow", "day_low")
                    hist = t.history(period="1d", interval="1m")
                if hist is not None and not hist.empty and "Close" in hist.columns:
                    hist = hist.copy()
                    hist.index = _to_taipei_naive(hist.index)
                    last = float(hist["Close"].iloc[-1])
                    o = float(hist["Open"].iloc[0]) if "Open" in hist.columns else o
                    h = float(hist["High"].max()) if "High" in hist.columns else h
                    l = float(hist["Low"].min()) if "Low" in hist.columns else l
                    ts = pd.Timestamp(hist.index[-1]).to_pydatetime()
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=TZ)
                if last is None or last <= 0:
                    return None
                return Quote(
                    ticker=ticker,
                    last=last,
                    open=o,
                    high=h,
                    low=l,
                    prev_close=prev,
                    ts=ts or now_taipei(),
                    source=self.name,
                    delayed=True,
                )
            except Exception:
                return None

        return _cached(f"yahoo:last:{ticker}", POLL_SEC, _pull)

    def intraday(self, ticker: str) -> pd.DataFrame:
        ticker = ticker or INDEX_YAHOO

        def _pull() -> pd.DataFrame:
            try:
                import yfinance as yf

                with _yf_silent():
                    hist = yf.Ticker(ticker).history(period="1d", interval="1m")
            except Exception:
                return pd.DataFrame()
            if hist is None or hist.empty:
                return pd.DataFrame()
            out = hist.copy()
            out.index = _to_taipei_naive(out.index)
            keep = [c for c in ("Open", "High", "Low", "Close") if c in out.columns]
            return out[keep].dropna()

        return _cached(f"yahoo:1m:{ticker}", POLL_SEC, _pull)

    def session_bar(self, ticker: str) -> dict | None:
        q = self.last(ticker)
        df = self.intraday(ticker)
        if df is not None and not df.empty:
            return {
                "Open": float(df["Open"].iloc[0]) if "Open" in df.columns else float(df["Close"].iloc[0]),
                "High": float(df["High"].max()) if "High" in df.columns else float(df["Close"].max()),
                "Low": float(df["Low"].min()) if "Low" in df.columns else float(df["Close"].min()),
                "Close": float(df["Close"].iloc[-1]),
                "ts": pd.Timestamp(df.index[-1]),
            }
        if q is None:
            return None
        if q.open is None or q.high is None or q.low is None:
            return None
        return {
            "Open": float(q.open),
            "High": float(q.high),
            "Low": float(q.low),
            "Close": float(q.last),
            "ts": pd.Timestamp(q.ts) if q.ts is not None else pd.Timestamp(now_taipei()),
        }


class ShioajiFeed:
    """永豐 Shioaji plug-in. Quotes only — there is no place_order here.

    Later wiring (do not run until you say so):
      1. pip install shioaji
      2. copy paper/broker_secrets.example.json → paper/broker_secrets.json
      3. set quote.backend = shioaji (or QUOTE_BACKEND=shioaji)
      4. fill connect() login; subscribe TSE001 for 加權
      5. map 2330.TW → Contracts.Stocks.TSE.2330 ; 5314.TWO → OTC

    Simulation flag stays true until you explicitly go live.
    """

    name = "shioaji"
    label = "永豐 Shioaji（尚未接上）"
    delayed = False
    INDEX = INDEX_SHIOAJI

    def __init__(self) -> None:
        self.api = None

    def available(self) -> bool:
        try:
            import shioaji  # noqa: F401
        except ImportError:
            return False
        sec = (load_secrets().get("shioaji") or {})
        return bool(sec.get("api_key") and sec.get("secret_key"))

    def connect(self) -> None:
        # Intentionally not called by get_feed() yet.
        raise NotConfigured(
            "永豐尚未接上。要接時：pip install shioaji，填 paper/broker_secrets.json，"
            "再把 quote.backend 設成 shioaji。此模組只訂閱報價，不下單。"
        )

    def last(self, ticker: str) -> Quote | None:
        raise NotConfigured("ShioajiFeed.last 尚未接報價")

    def intraday(self, ticker: str) -> pd.DataFrame:
        raise NotConfigured("ShioajiFeed.intraday 尚未接報價")

    def session_bar(self, ticker: str) -> dict | None:
        raise NotConfigured("ShioajiFeed.session_bar 尚未接報價")

    @staticmethod
    def to_contract_id(ticker: str) -> str:
        if ticker in (INDEX_YAHOO, "TWII", INDEX_SHIOAJI):
            return INDEX_SHIOAJI
        return ticker.split(".")[0]


class QuoteFeed:
    """Facade: yahoo now, shioaji when you flip the switch and it actually connects."""

    def __init__(self) -> None:
        self.wanted = _backend_name()
        self.fallback = False
        if self.wanted == "shioaji":
            sj = ShioajiFeed()
            if sj.available():
                # Still do not auto-login. When you are ready, replace this branch
                # with: sj.connect(); self.impl = sj
                self.impl = YahooFeed()
                self.fallback = True
            else:
                self.impl = YahooFeed()
                self.fallback = True
        else:
            self.impl = YahooFeed()

    @property
    def name(self) -> str:
        return self.impl.name

    @property
    def label(self) -> str:
        if self.wanted == "shioaji":
            return "Yahoo（永豐接點已留，尚未登入）"
        return self.impl.label

    @property
    def delayed(self) -> bool:
        return bool(getattr(self.impl, "delayed", True))

    def last(self, ticker: str) -> Quote | None:
        return self.impl.last(ticker)

    def intraday(self, ticker: str) -> pd.DataFrame:
        return self.impl.intraday(ticker)

    def session_bar(self, ticker: str) -> dict | None:
        return self.impl.session_bar(ticker)


def get_feed() -> QuoteFeed:
    return QuoteFeed()


def apply_session_bar(daily: pd.DataFrame, bar: dict | None, day=None) -> pd.DataFrame:
    """Replace or append today's OHLC on the daily TWII frame."""
    if daily is None or daily.empty or not bar:
        return daily
    day = pd.Timestamp(day if day is not None else now_taipei().date()).normalize()
    out = daily.copy()
    out.index = pd.to_datetime(out.index).normalize()
    for col in ("Open", "High", "Low", "Close"):
        if col not in out.columns:
            out[col] = pd.NA
    out.loc[day, "Open"] = float(bar["Open"])
    out.loc[day, "High"] = float(bar["High"])
    out.loc[day, "Low"] = float(bar["Low"])
    out.loc[day, "Close"] = float(bar["Close"])
    return out.sort_index()
