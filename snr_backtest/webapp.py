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

from config import INDEX_TICKER, INITIAL_CAPITAL, REPORTS_DIR, STRATEGY_DEFAULTS
from data import get_price, load_cache
from indicators import pack_curves
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
        interval = 2.0 if in_txf_night() else (5.0 if in_cash_session() else 10.0)
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


BT_LABELS = {
    "breakout_v2": "breakout_v2（現行紙上）",
    "breakout_v1": "breakout_v1（SNR 突破）",
    "breakout_raw": "突破（無 SNR）",
    "pullback_v1": "pullback_v1（回檔）",
    "pullback_raw": "回檔（無 SNR）",
}


def _bt_names() -> list[dict]:
    out = []
    if not REPORTS_DIR.exists():
        return out
    for p in sorted(REPORTS_DIR.glob("*_equity.csv")):
        key = p.name.replace("_equity.csv", "")
        out.append({"id": key, "label": BT_LABELS.get(key, key)})
    return out


def _bt_payload(name: str) -> dict:
    key = "".join(ch for ch in name if ch.isalnum() or ch in "_-")
    eq_path = REPORTS_DIR / f"{key}_equity.csv"
    sm_path = REPORTS_DIR / f"{key}_summary.csv"
    tr_path = REPORTS_DIR / f"{key}_trades.csv"
    curve = []
    if eq_path.exists():
        import pandas as pd

        df = pd.read_csv(eq_path, encoding="utf-8-sig")
        if "date" in df.columns:
            col = "total" if "total" in df.columns else df.columns[-1]
            first = None
            for _, row in df.iterrows():
                d = str(row.get("date") or "")[:10]
                v = row.get(col)
                if v is None or d == "" or d == "nan":
                    continue
                try:
                    fv = float(v)
                except (TypeError, ValueError):
                    continue
                if first is None or first == 0:
                    first = fv
                curve.append({"time": d, "value": round(fv / first * 100, 2) if first else fv})
    summary = []
    if sm_path.exists():
        summary = _csv_rows(sm_path)
        keep = []
        for row in summary:
            t = str(row.get("ticker") or "")
            if t.startswith("EQUAL") or t == "EQUAL_WEIGHT":
                keep.append(row)
        if keep:
            summary = keep[-2:]
        else:
            summary = summary[-1:]
    trades = _csv_rows(tr_path, 40) if tr_path.exists() else []
    return {
        "id": key,
        "label": BT_LABELS.get(key, key),
        "curve": curve,
        "summary": summary,
        "trades": trades,
        "note": "用 data\\ 快取回測，不是紙上帳戶。不成交。",
    }


@app.get("/api/backtest")
def api_backtest_list() -> JSONResponse:
    return JSONResponse({"items": _bt_names()})


class BtRunIn(BaseModel):
    kind: str = "breakout"
    start: str = "2021-08-13"
    end: str = "2026-08-13"
    tp: float = 0.25
    sl: float = 0.20
    time_stop_days: int = 3
    snr_min: float = 0.40
    snr_max: float = 0.25
    twii_filter: bool = True
    trail: bool = True
    trail_arm: float = 0.12
    trail_lookback: int = 15
    use_snr: bool = True
    lookback: int = 20
    sma_fast: int = 20
    sma_trend: int = 60
    band_lo: float = 0.97
    band_hi: float = 1.01
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    rsi_n: int = 14
    rsi_os: float = 30.0
    rsi_ob: float = 70.0
    kd_n: int = 9
    kd_k: int = 3
    kd_d: int = 3
    kd_os: float = 20.0
    kd_ob: float = 80.0
    bb_n: int = 20
    bb_k: float = 2.0
    bb_mode: str = "revert"


@app.post("/api/backtest/run")
def api_backtest_run(body: BtRunIn) -> JSONResponse:
    """Run on cached daily bars. Does not touch paper/account.json."""
    import pandas as pd

    from config import END_DATE, INDEX_TICKER, START_DATE, TICKERS
    from engine import run_universe
    from metrics import combined_equity, summarize_one
    from strategies import StrategySpec

    kind = (body.kind or "breakout").strip().lower()
    allowed = ("breakout", "pullback", "macd", "rsi", "kd", "sma", "bb")
    if kind not in allowed:
        return JSONResponse({"ok": False, "error": "kind 要是 " + " / ".join(allowed)}, status_code=400)
    spec = StrategySpec(
        name=f"live_{kind}",
        tp=float(body.tp),
        sl=float(body.sl),
        time_stop_days=int(body.time_stop_days or 0),
        use_snr=bool(body.use_snr) if kind in ("breakout", "pullback") else False,
        kind=kind,
        snr_min=float(body.snr_min),
        snr_max=float(body.snr_max),
        twii_filter=bool(body.twii_filter) if kind == "breakout" else False,
        trail=bool(body.trail) if kind == "breakout" else False,
        trail_arm=float(body.trail_arm),
        trail_lookback=int(body.trail_lookback),
        lookback=int(body.lookback),
        sma_fast=int(body.sma_fast),
        sma_trend=int(body.sma_trend),
        band_lo=float(body.band_lo),
        band_hi=float(body.band_hi),
        macd_fast=int(body.macd_fast),
        macd_slow=int(body.macd_slow),
        macd_signal=int(body.macd_signal),
        rsi_n=int(body.rsi_n),
        rsi_os=float(body.rsi_os),
        rsi_ob=float(body.rsi_ob),
        kd_n=int(body.kd_n),
        kd_k=int(body.kd_k),
        kd_d=int(body.kd_d),
        kd_os=float(body.kd_os),
        kd_ob=float(body.kd_ob),
        bb_n=int(body.bb_n),
        bb_k=float(body.bb_k),
        bb_mode=(body.bb_mode or "revert").strip().lower(),
    )
    prices: dict = {}
    for t in list(TICKERS.keys()) + [INDEX_TICKER]:
        try:
            df = load_cache(t, end_date=None)
        except Exception:
            df = None
        if df is not None and not df.empty:
            prices[t] = df
    if len(prices) < 2:
        return JSONResponse({"ok": False, "error": "快取不夠，先讓紙上跑過下載。"}, status_code=400)
    start = body.start or START_DATE
    end = body.end or END_DATE
    results = run_universe(prices, spec, start_date=start, end_date=end, twii=prices.get(INDEX_TICKER))
    total = combined_equity(results)
    fake = type("R", (), {})()
    fake.ticker = "EQUAL_WEIGHT"
    fake.name = "等權合計"
    fake.trades = __import__("pandas").concat(
        [r.trades for r in results if r.trades is not None and len(r.trades)],
        ignore_index=True,
    ) if any(r.trades is not None and len(r.trades) for r in results) else __import__("pandas").DataFrame()
    fake.equity = total
    fake.initial_capital = sum(r.initial_capital for r in results) or 10_000_000.0
    fake.failed = ""
    row = summarize_one(fake)
    curve = []
    if total is not None and len(total):
        first = float(total.iloc[0]) or 1.0
        for ts, v in total.items():
            curve.append({"time": str(pd.Timestamp(ts).date()), "value": round(float(v) / first * 100, 2)})
    trades = []
    if fake.trades is not None and len(fake.trades):
        trades = json.loads(fake.trades.tail(40).to_json(orient="records", date_format="iso"))
    return JSONResponse({
        "ok": True,
        "id": spec.name,
        "label": kind,
        "curve": curve,
        "summary": [row],
        "trades": trades,
        "note": f"快取重跑 {start}～{end}，十檔等權。不成交、不改紙上帳戶。",
        "params": spec.param_dict() | {
            "kind": kind, "tp": spec.tp, "sl": spec.sl,
            "time_stop_days": spec.time_stop_days, "lookback": spec.lookback,
            "macd": [spec.macd_fast, spec.macd_slow, spec.macd_signal],
            "rsi": [spec.rsi_n, spec.rsi_os, spec.rsi_ob],
            "kd": [spec.kd_n, spec.kd_k, spec.kd_d, spec.kd_os, spec.kd_ob],
            "sma": [spec.sma_fast, spec.sma_trend],
            "bb": [spec.bb_n, spec.bb_k, spec.bb_mode],
        },
    })


@app.get("/api/backtest/{name}")
def api_backtest_one(name: str) -> JSONResponse:
    return JSONResponse(_bt_payload(name))


@app.get("/api/curves")
def api_curves(ticker: str = "^TWII", n: int = 132) -> JSONResponse:
    t = (ticker or "^TWII").strip()
    if t.upper() in ("TWII", "TAIEX"):
        t = INDEX_TICKER
    df = None
    try:
        df = load_cache(t, end_date=None)
    except Exception:
        df = None
    payload = pack_curves(df, n=max(22, min(int(n or 132), 260)))
    payload["ticker"] = t
    payload["name"] = display_name(t) if t != INDEX_TICKER else "台灣加權"
    return JSONResponse(payload)


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
