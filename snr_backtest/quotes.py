"""Live quotes for the dashboard and alerts.

Backends
  yahoo    delayed ~15 minutes. No account.
  shioaji  永豐模擬環境報價（simulation=true 強制）。填 paper/broker_secrets.json。
           此模組沒有 place_order / activate_ca。不下真單。

Paper fills stay t close / t+1 open in paper_daily.py.
"""
from __future__ import annotations

import atexit
import contextlib
import io
import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

log = logging.getLogger("trade.quotes")

import pandas as pd

ROOT = Path(__file__).resolve().parent
PAPER = ROOT / "paper"
SECRETS_PATH = PAPER / "broker_secrets.json"
TZ = ZoneInfo("Asia/Taipei")
INDEX_YAHOO = "^TWII"
INDEX_SHIOAJI = "IX0001"  # 發行量加權股價指數（舊代碼 TSE001 在 contracts v2 已不用）

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


def _shioaji_keys(sec: dict | None = None) -> tuple[str, str]:
    sec = sec if sec is not None else (load_secrets().get("shioaji") or {})
    key = str(sec.get("api_key") or os.environ.get("SJ_API_KEY") or "").strip()
    secret = str(sec.get("secret_key") or os.environ.get("SJ_SEC_KEY") or "").strip()
    return key, secret


def _simulation_forced(sec: dict | None = None) -> bool:
    """This project never logs into production trading."""
    sec = sec if sec is not None else (load_secrets().get("shioaji") or {})
    raw = sec.get("simulation", True)
    if raw is False or str(raw).strip().lower() in ("0", "false", "no"):
        return False
    return True


def _backend_name() -> str:
    env = (os.environ.get("QUOTE_BACKEND") or "").strip().lower()
    if env in ("yahoo", "shioaji"):
        return env
    try:
        from ui_settings import load_raw

        raw = (load_raw().get("quote") or {}).get("backend")
        if str(raw or "").strip().lower() in ("yahoo", "shioaji"):
            return str(raw).strip().lower()
    except Exception:
        pass
    data = load_secrets()
    key, secret = _shioaji_keys(data.get("shioaji") or {})
    file_b = str(data.get("backend") or "").strip().lower()
    if key and secret:
        if file_b in ("yahoo", "shioaji"):
            return file_b
        return "shioaji"
    if file_b in ("yahoo", "shioaji"):
        return file_b
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


def _num(obj, *names) -> float | None:
    for n in names:
        try:
            v = obj[n] if isinstance(obj, dict) else getattr(obj, n, None)
        except Exception:
            v = None
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if f > 0:
            return f
    return None


def _parse_ts(raw) -> datetime:
    if raw is None:
        return now_taipei()
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=TZ)
        return raw.astimezone(TZ)
    try:
        n = int(raw)
        if n > 10**15:
            n = n / 1e9
        return datetime.fromtimestamp(n, tz=TZ)
    except (TypeError, ValueError, OSError):
        try:
            ts = pd.Timestamp(raw)
            if ts.tzinfo is None:
                ts = ts.tz_localize(TZ)
            return ts.to_pydatetime()
        except Exception:
            return now_taipei()


class ShioajiFeed:
    """永豐模擬環境報價。沒有 place_order。simulation 不是 true 就拒絕登入。"""

    name = "shioaji"
    label = "永豐 Shioaji 模擬"
    delayed = False
    INDEX = INDEX_SHIOAJI

    def __init__(self) -> None:
        self.api = None
        self._lock = threading.Lock()
        self._ticks: dict[str, Quote] = {}
        self._sub: set[str] = set()
        self._yahoo = YahooFeed()

    def available(self) -> bool:
        try:
            import shioaji  # noqa: F401
        except ImportError:
            return False
        key, secret = _shioaji_keys()
        return bool(key and secret)

    def connect(self) -> None:
        if self.api is not None:
            return
        with self._lock:
            if self.api is not None:
                return
            if not _simulation_forced():
                raise NotConfigured("此專案只准 simulation=true，不下真單。請改 broker_secrets.json")
            try:
                import shioaji as sj
            except ImportError as exc:
                raise NotConfigured("尚未 pip install shioaji") from exc
            key, secret = _shioaji_keys()
            if not key or not secret:
                raise NotConfigured(
                    "沒有 API Key。複製 paper/broker_secrets.example.json → "
                    "paper/broker_secrets.json 再填 api_key / secret_key"
                )
            api = sj.Shioaji(simulation=True)
            log.info("shioaji login simulation=True (quotes only, no orders)")
            api.login(api_key=key, secret_key=secret)
            self._bind_ticks(api)
            self.api = api
            atexit.register(self._logout)

    def _logout(self) -> None:
        api = self.api
        self.api = None
        if api is None:
            return
        try:
            api.logout()
        except Exception:
            pass

    def _bind_ticks(self, api) -> None:
        def _store(tick) -> None:
            code = str(getattr(tick, "code", "") or "")
            last = _num(tick, "close", "price", "last_price")
            if not code or not last:
                return
            open_ = _num(tick, "open", "open_price")
            high = _num(tick, "high", "high_price")
            low = _num(tick, "low", "low_price")
            prev = None
            chg = getattr(tick, "change_price", None)
            try:
                if chg is not None:
                    prev = last - float(chg)
                    if prev <= 0:
                        prev = None
            except (TypeError, ValueError):
                prev = None
            q = Quote(
                ticker=code,
                last=last,
                open=open_,
                high=high,
                low=low,
                prev_close=prev,
                ts=_parse_ts(getattr(tick, "datetime", None) or getattr(tick, "ts", None)),
                source=self.name,
                delayed=False,
            )
            self._ticks[code] = q
            if code == INDEX_SHIOAJI:
                self._ticks[INDEX_YAHOO] = q

        def _cb(data):
            _store(data)

        try:
            api.set_on_tick_stk_v1_callback(_cb)
        except Exception as exc:
            log.warning("shioaji tick callback: %s", exc)
        try:
            api.set_on_quote_idx_v1_callback(_cb)
        except Exception as exc:
            log.warning("shioaji idx callback: %s", exc)

    def contract(self, ticker: str):
        self.connect()
        api = self.api
        code = self.to_contract_id(ticker)
        getter = getattr(getattr(api, "contracts", None), "get", None)
        if callable(getter):
            try:
                c = getter(code)
                if c is not None:
                    return c
            except Exception:
                pass
        return None

    def _subscribe(self, ticker: str) -> None:
        code = self.to_contract_id(ticker)
        if code in self._sub:
            return
        c = self.contract(ticker)
        if c is None:
            return
        try:
            if hasattr(self.api, "subscribe"):
                self.api.subscribe(c, quote_type="tick")
            else:
                self.api.quote.subscribe(c, quote_type="tick")
            self._sub.add(code)
        except Exception as exc:
            log.warning("shioaji subscribe %s: %s", code, exc)

    def last(self, ticker: str) -> Quote | None:
        ticker = ticker or INDEX_YAHOO
        code = self.to_contract_id(ticker)
        try:
            self.connect()
            self._subscribe(ticker)
        except Exception as exc:
            log.warning("shioaji last fallback yahoo (%s): %s", ticker, exc)
            return self._yahoo.last(ticker)
        hit = self._ticks.get(code) or self._ticks.get(ticker)
        if hit is not None:
            return hit

        def _snap() -> Quote | None:
            c = self.contract(ticker)
            if c is None:
                return None
            snaps = self.api.snapshots([c])
            if not snaps:
                return None
            s = snaps[0]
            last = _num(s, "close", "price")
            if not last:
                return None
            prev = None
            chg = getattr(s, "change_price", None)
            try:
                if chg is not None:
                    prev = last - float(chg)
                    if prev <= 0:
                        prev = None
            except (TypeError, ValueError):
                prev = None
            q = Quote(
                ticker=ticker,
                last=last,
                open=_num(s, "open"),
                high=_num(s, "high"),
                low=_num(s, "low"),
                prev_close=prev,
                ts=_parse_ts(getattr(s, "ts", None) or getattr(s, "datetime", None)),
                source=self.name,
                delayed=False,
            )
            self._ticks[code] = q
            return q

        try:
            return _cached(f"sj:snap:{code}", POLL_SEC, _snap)
        except Exception as exc:
            log.warning("shioaji snapshot fallback yahoo (%s): %s", ticker, exc)
            return self._yahoo.last(ticker)

    def intraday(self, ticker: str) -> pd.DataFrame:
        ticker = ticker or INDEX_YAHOO
        day = now_taipei().strftime("%Y-%m-%d")

        def _pull() -> pd.DataFrame:
            try:
                self.connect()
                c = self.contract(ticker)
                if c is None:
                    return pd.DataFrame()
                raw = self.api.kbars(c, start=day, end=day)
                if raw is None:
                    return pd.DataFrame()
                if isinstance(raw, pd.DataFrame):
                    df = raw.copy()
                else:
                    df = pd.DataFrame(raw)
                if df is None or df.empty:
                    return pd.DataFrame()
                if "ts" in df.columns:
                    df.index = pd.to_datetime(df["ts"])
                df.index = _to_taipei_naive(pd.DatetimeIndex(df.index))
                keep = [c for c in ("Open", "High", "Low", "Close") if c in df.columns]
                if len(keep) < 4:
                    lower = {str(c).lower(): c for c in df.columns}
                    mapped = {}
                    for need in ("Open", "High", "Low", "Close"):
                        src = lower.get(need.lower())
                        if src is not None:
                            mapped[need] = df[src]
                    df = pd.DataFrame(mapped, index=df.index) if mapped else df
                    keep = [c for c in ("Open", "High", "Low", "Close") if c in df.columns]
                return df[keep].dropna() if keep else pd.DataFrame()
            except Exception as exc:
                log.warning("shioaji kbars fallback yahoo (%s): %s", ticker, exc)
                return self._yahoo.intraday(ticker)

        return _cached(f"sj:1m:{ticker}", POLL_SEC, _pull)

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
        if q is None or q.open is None or q.high is None or q.low is None:
            return None
        return {
            "Open": float(q.open),
            "High": float(q.high),
            "Low": float(q.low),
            "Close": float(q.last),
            "ts": pd.Timestamp(q.ts) if q.ts is not None else pd.Timestamp(now_taipei()),
        }

    @staticmethod
    def to_contract_id(ticker: str) -> str:
        if ticker in (INDEX_YAHOO, "TWII", INDEX_SHIOAJI, "^TWII"):
            return INDEX_SHIOAJI
        return str(ticker).split(".")[0]


class QuoteFeed:
    """yahoo, or shioaji simulation quotes. Never production orders."""

    def __init__(self) -> None:
        self.wanted = _backend_name()
        self.fallback = False
        if self.wanted == "shioaji":
            sj = ShioajiFeed()
            if not sj.available():
                try:
                    import shioaji  # noqa: F401
                    why = "API Key 空白或讀不到 broker_secrets.json"
                except ImportError:
                    why = "尚未安裝 shioaji（請用 .venv 跑 python quotes.py）"
                log.warning("shioaji requested but %s; using Yahoo", why)
                self.impl = YahooFeed()
                self.fallback = True
                return
            try:
                sj.connect()
                self.impl = sj
            except Exception as exc:
                log.warning("shioaji login failed, using Yahoo: %s", exc)
                self.impl = YahooFeed()
                self.fallback = True
        else:
            self.impl = YahooFeed()

    @property
    def name(self) -> str:
        return self.impl.name

    @property
    def label(self) -> str:
        if self.wanted == "shioaji" and self.fallback:
            return "Yahoo（永豐未接上，已退回）"
        return getattr(self.impl, "label", self.impl.name)

    @property
    def delayed(self) -> bool:
        return bool(getattr(self.impl, "delayed", True))

    def last(self, ticker: str) -> Quote | None:
        return self.impl.last(ticker)

    def intraday(self, ticker: str) -> pd.DataFrame:
        return self.impl.intraday(ticker)

    def session_bar(self, ticker: str) -> dict | None:
        return self.impl.session_bar(ticker)


_feed_lock = threading.Lock()
_feed: QuoteFeed | None = None


def get_feed() -> QuoteFeed:
    global _feed
    with _feed_lock:
        if _feed is None:
            _feed = QuoteFeed()
        return _feed


def ping() -> dict:
    """Login check. Never prints secrets."""
    wanted = _backend_name()
    keys = bool(_shioaji_keys()[0] and _shioaji_keys()[1])
    out = {
        "wanted": wanted,
        "has_keys": keys,
        "simulation_required": True,
        "simulation_ok": _simulation_forced(),
        "secrets_path": str(SECRETS_PATH),
        "secrets_exists": SECRETS_PATH.exists(),
    }
    feed = get_feed()
    out["active"] = feed.name
    out["label"] = feed.label
    out["fallback"] = feed.fallback
    q = feed.last(INDEX_YAHOO)
    out["twii_last"] = None if q is None else q.last
    out["twii_source"] = None if q is None else q.source
    return out


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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(json.dumps(ping(), ensure_ascii=False, indent=2, default=str))
