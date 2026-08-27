"""Local HTML dashboard with WebSocket live updates. Not Streamlit. Not a broker."""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
WEB = ROOT / "web"
PAPER = ROOT / "paper"

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import INDEX_TICKER, INITIAL_CAPITAL, STRATEGY_DEFAULTS
from data import get_price, load_cache
from quotes import (
    INDEX_YAHOO,
    apply_session_bar,
    get_feed,
    in_cash_session,
    in_txf_night,
    now_taipei,
    txf_night_payload,
)
from ui_settings import (
    TICKER_RE,
    effective_news,
    effective_strategy,
    load_raw,
    reset_all,
    save_raw,
    save_strategy,
    save_watchlist,
)
from universe import BANK_TICKERS, candidate_tickers, default_catalog, display_name

WATCH = [
    PAPER / "account.json",
    PAPER / "alerts.csv",
    PAPER / "news_risk.json",
    PAPER / "news_snapshot_2130.json",
    PAPER / "equity.csv",
    PAPER / "ledger.csv",
    PAPER / "ui_settings.json",
    PAPER / "last_live_run.txt",
    PAPER / "last_alert_session.txt",
    PAPER / "last_news_0830.txt",
    PAPER / "last_news_2130.txt",
    PAPER / "news_journal.csv",
    PAPER / "size_journal.csv",
]

app = FastAPI(title="TW Paper Dashboard")
clients: set[WebSocket] = set()


def _json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _csv_rows(path: Path, n: int | None = None) -> list[dict]:
    if not path.exists():
        return []
    try:
        import pandas as pd

        df = pd.read_csv(path, encoding="utf-8-sig")
    except OSError:
        return []
    if df.empty:
        return []
    if n:
        df = df.tail(n)
    return json.loads(df.to_json(orient="records", date_format="iso"))


def last_close(ticker: str) -> tuple[float | None, str]:
    try:
        df = load_cache(ticker, end_date=None)
    except Exception:
        df = None
    if df is None or df.empty or "Close" not in df.columns:
        return None, ""
    close = df["Close"].dropna()
    if close.empty:
        return None, ""
    return float(close.iloc[-1]), str(__import__("pandas").Timestamp(close.index.max()).date())


def last_mark(ticker: str) -> tuple[float | None, str]:
    """Live last if Yahoo has it; else last daily close. Not a broker fill."""
    try:
        q = get_feed().last(ticker)
    except Exception:
        q = None
    if q is not None and q.last:
        ts = ""
        if q.ts:
            ts = q.ts.strftime("%H:%M:%S") if in_cash_session() else q.ts.strftime("%Y-%m-%d %H:%M")
        return float(q.last), ts
    return last_close(ticker)


def twii_payload(sma_n: int) -> dict[str, Any]:
    import pandas as pd

    try:
        df = load_cache(INDEX_TICKER, end_date=None)
    except Exception:
        df = None
    out: dict[str, Any] = {
        "last": None, "open": None, "high": None, "low": None, "close": None,
        "chg": None, "chg_pct": None, "asof": "",
        "status": "盤後", "source": "", "above": None, "sma_n": sma_n,
        "candles": [],
    }
    if df is None or df.empty:
        return out
    daily = df.copy()
    daily.index = pd.to_datetime(daily.index).normalize()
    need = [c for c in ("Open", "High", "Low", "Close") if c in daily.columns]
    if len(need) < 4:
        return out
    daily = daily[need].dropna()
    feed = get_feed()
    live = in_cash_session()
    out["status"] = "盤中" if live else "盤後"
    out["source"] = ""
    if live:
        q = feed.last(INDEX_YAHOO)
        bar = feed.session_bar(INDEX_YAHOO)
        if bar:
            daily = apply_session_bar(daily, bar, now_taipei().date())
        if q is not None:
            last = float(q.last)
            prev = float(q.prev_close) if q.prev_close else float(daily["Close"].iloc[-2]) if len(daily) > 1 else last
            out["last"] = last
            out["chg"] = last - prev
            out["chg_pct"] = (last - prev) / prev * 100 if prev else 0.0
            out["asof"] = q.ts.strftime("%H:%M:%S") if q.ts else ""
    if out["last"] is None:
        last = float(daily["Close"].iloc[-1])
        prev = float(daily["Close"].iloc[-2]) if len(daily) > 1 else last
        out["last"] = last
        out["chg"] = last - prev
        out["chg_pct"] = (last - prev) / prev * 100 if prev else 0.0
        out["asof"] = str(pd.Timestamp(daily.index.max()).date())
    row = daily.iloc[-1]
    out["open"] = float(row["Open"])
    out["high"] = float(row["High"])
    out["low"] = float(row["Low"])
    out["close"] = float(out["last"] if out["last"] is not None else row["Close"])
    sma = daily["Close"].rolling(int(sma_n), min_periods=int(sma_n)).mean()
    last = float(out["last"])
    sma_now = sma.iloc[-1] if len(sma) else None
    out["above"] = bool(pd.notna(sma_now) and last > float(sma_now)) if sma_now is not None else None
    view = daily.tail(260)
    sma_v = sma.reindex(view.index)
    candles = []
    for ts, row in view.iterrows():
        candles.append({
            "time": pd.Timestamp(ts).strftime("%Y-%m-%d"),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "sma": (None if pd.isna(sma_v.loc[ts]) else float(sma_v.loc[ts])),
        })
    out["candles"] = candles
    return out


def build_state() -> dict[str, Any]:
    import pandas as pd

    acct = _json(PAPER / "account.json")
    news = _json(PAPER / "news_risk.json")
    snap = _json(PAPER / "news_snapshot_2130.json")
    catalog = default_catalog()
    watch = candidate_tickers()
    held = {
        p.get("ticker"): p
        for p in (acct.get("positions") or [])
        if p.get("ticker") and int(p.get("shares") or 0) > 0
    }
    strat = effective_strategy(STRATEGY_DEFAULTS)
    news_th = effective_news()
    cash = float(acct.get("cash") or 0)
    initial = float(acct.get("initial_cash") or INITIAL_CAPITAL)
    day = now_taipei().strftime("%Y-%m-%d")
    alerts = []
    for row in _csv_rows(PAPER / "alerts.csv"):
        t = str(row.get("time") or "")
        if t.startswith(day):
            alerts.append(row)
    positions = []
    mv_sum = 0.0
    for p in acct.get("positions") or []:
        ticker = p.get("ticker")
        shares = int(p.get("shares") or 0)
        avg = float(p.get("avg_price") or 0)
        last, asof = last_mark(ticker)
        last = last if last is not None else avg
        mv = last * shares
        mv_sum += mv
        upnl = (last - avg) * shares
        upct = (last / avg - 1.0) * 100 if avg else 0.0
        positions.append({
            "ticker": ticker,
            "name": p.get("name") or display_name(ticker),
            "shares": shares,
            "avg": round(avg, 2),
            "last": round(last, 2),
            "mv": round(mv, 0),
            "upnl": round(upnl, 0),
            "upct": round(upct, 1),
            "entry_date": p.get("entry_date") or "",
            "trail": bool(p.get("trail_armed")),
            "asof": asof,
        })
    equity = cash + mv_sum if positions else float(acct.get("equity") or cash)
    pnl = equity - initial
    watch_rows = []
    seen = set()
    for t, n in catalog.items():
        watch_rows.append({"ticker": t, "name": watch.get(t, n), "on": t in watch, "held": t in held})
        seen.add(t)
    for t, n in watch.items():
        if t in seen:
            continue
        watch_rows.append({"ticker": t, "name": n, "on": True, "held": t in held})
    eq_curve = []
    for row in _csv_rows(PAPER / "equity.csv"):
        eq_curve.append({"date": str(row.get("date") or "")[:10], "equity": row.get("equity")})
    allow = bool(news.get("allow_new_entries"))
    lock_new = bool(news.get("lock_new", not allow))
    size_w = news.get("size_weight")
    return {
        "clock": now_taipei().strftime("%Y-%m-%d %H:%M:%S"),
        "live": in_cash_session(),
        "equity": equity,
        "cash": cash,
        "pnl": pnl,
        "pnl_pct": (pnl / initial * 100) if initial else 0.0,
        "n_pos": len(held),
        "session": acct.get("last_session") or "—",
        "heat": news.get("news_score"),
        "trend": news.get("trend") or "—",
        "lock_new": lock_new,
        "size_weight": size_w,
        "allow": allow,
        "reason": news.get("reason") or "",
        "off_headlines": news.get("off_headlines") or [],
        "on_headlines": news.get("on_headlines") or [],
        "snap": {
            "score": snap.get("news_score"),
            "session": snap.get("session"),
            "note": snap.get("note") or "",
            "off": (snap.get("off_headlines") or [])[:12],
        },
        "alerts": alerts,
        "pending": acct.get("pending") or [],
        "positions": positions,
        "stamps": {
            "live": _text(PAPER / "last_live_run.txt"),
            "alert": _text(PAPER / "last_alert_session.txt"),
            "n0830": _text(PAPER / "last_news_0830.txt"),
            "n2130": _text(PAPER / "last_news_2130.txt"),
        },
        "twii": twii_payload(int(strat.get("TWII_SMA") or 60)),
        "txf_night": txf_night_payload(),
        "equity_curve": eq_curve,
        "ledger": _csv_rows(PAPER / "ledger.csv", 30),
        "journal": _csv_rows(PAPER / "news_journal.csv", 40),
        "watch": watch_rows,
        "strategy": strat,
        "news_th": news_th,
        "held_banks": [BANK_TICKERS[t] for t in held if t in BANK_TICKERS],
    }


def _mtimes() -> tuple:
    out = []
    for p in WATCH:
        try:
            out.append(p.stat().st_mtime if p.exists() else 0.0)
        except OSError:
            out.append(0.0)
    return tuple(out)


async def broadcaster() -> None:
    last = None
    last_push = 0.0
    while True:
        await asyncio.sleep(1.0)
        sig = _mtimes()
        now = datetime.now().timestamp()
        interval = 5.0 if (in_cash_session() or in_txf_night()) else 10.0
        due = sig != last or (now - last_push >= interval)
        if not due or not clients:
            continue
        last = sig
        last_push = now
        try:
            payload = json.dumps({"type": "state", "data": build_state()}, ensure_ascii=False, default=str)
        except Exception:
            continue
        dead = []
        for ws in list(clients):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            clients.discard(ws)


@app.on_event("startup")
async def _startup() -> None:
    asyncio.create_task(broadcaster())


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


@app.get("/api/state")
def api_state() -> JSONResponse:
    return JSONResponse(build_state())


class WatchIn(BaseModel):
    items: list[dict] = Field(default_factory=list)


class AddTickerIn(BaseModel):
    ticker: str
    name: str = ""


class StratIn(BaseModel):
    strategy: dict
    news: dict | None = None


@app.post("/api/watch")
def api_watch(body: WatchIn) -> dict:
    nxt: dict[str, str] = {}
    for row in body.items:
        t = str(row.get("ticker") or "").strip().upper()
        if not TICKER_RE.match(t) or t in BANK_TICKERS:
            continue
        if row.get("on"):
            nxt[t] = str(row.get("name") or t).strip() or t
    save_watchlist(nxt)
    return {"ok": True, "n": len(nxt)}


@app.post("/api/watch/add")
def api_watch_add(body: AddTickerIn) -> dict:
    t = body.ticker.strip().upper()
    if not TICKER_RE.match(t):
        return {"ok": False, "error": "代號要像 2330.TW 或 5314.TWO"}
    if t in BANK_TICKERS:
        return {"ok": False, "error": "銀行／金控不列入監測"}
    name = (body.name or "").strip() or default_catalog().get(t) or t
    cur = dict(candidate_tickers())
    cur[t] = name
    try:
        get_price(t, force_download=True, end_date=None)
    except Exception:
        pass
    try:
        save_watchlist(cur)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "ticker": t, "name": name}


@app.post("/api/watch/reset")
def api_watch_reset() -> dict:
    data = load_raw()
    data.pop("watchlist", None)
    save_raw(data)
    return {"ok": True}


@app.post("/api/strategy")
def api_strategy(body: StratIn) -> dict:
    save_strategy(body.strategy, news=body.news)
    return {"ok": True}


@app.post("/api/strategy/reset")
def api_strategy_reset() -> dict:
    reset_all()
    return {"ok": True}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    clients.add(ws)
    try:
        try:
            payload = json.dumps({"type": "state", "data": build_state()}, ensure_ascii=False, default=str)
        except Exception:
            payload = json.dumps({"type": "state", "data": {}})
        await ws.send_text(payload)
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        clients.discard(ws)


app.mount("/static", StaticFiles(directory=str(WEB)), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("webapp:app", host="127.0.0.1", port=8501, reload=False)
