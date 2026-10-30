r"""NN 紙上帳戶面板（FastAPI）。只讀檔案、只模擬，不是券商、不下單。

http://127.0.0.1:8501 ；交易教練（trade-coach, :7870）以浮動聊天泡泡嵌入每一頁。
"""
from __future__ import annotations

import csv
import time
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
WEB = ROOT / "web"
PAPER = ROOT / "paper_nn"
COACH_URL = "http://localhost:7870"
NAMES_FILE = Path(r"D:\trade-coach\data\stock_list.json")

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

import nn_strategy
import stock_names  # noqa: E402

app = FastAPI(title="NN 紙上帳戶")
app.mount("/static", StaticFiles(directory=str(WEB)), name="static")


@app.middleware("http")
async def _no_cache(request, call_next):  # 避免瀏覽器拿到舊版 app.js
    resp = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith(("/static/", "/api/")):
        resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


# ---- 行情條：背景執行緒每 30 秒更新（永豐模擬報價，無金鑰時 quotes 自動改 Yahoo），/api/ticker 只讀快取 ----
import threading  # noqa: E402

TICKER: dict = {"taiex": {"ok": False, "reason": "載入中"}, "txf": {"ok": False, "reason": "載入中"}, "updated": None}


def _ticker_once() -> None:
    from quotes import get_feed, now_taipei, txf_night_payload, in_txf_night
    out = {}
    try:
        q = get_feed().last("^TWII")
        if q and q.last and q.prev_close:
            out["taiex"] = {"ok": True, "last": q.last, "chg": q.last - q.prev_close,
                            "pct": (q.last / q.prev_close - 1) * 100, "ts": q.ts.strftime("%m-%d %H:%M") if q.ts else "",
                            "source": q.source, "delayed": bool(q.delayed)}
        else:
            out["taiex"] = {"ok": False, "reason": "報價來源沒有回資料"}
    except Exception as exc:  # noqa: BLE001
        out["taiex"] = {"ok": False, "reason": f"報價失敗：{type(exc).__name__}"}
    try:
        from quotes import in_cash_session, TXF_FRONT
        nowt = now_taipei()
        if nowt.weekday() < 5 and (8, 45) <= (nowt.hour, nowt.minute) < (13, 45):
            fq = get_feed().last(TXF_FRONT)
            if fq and fq.last:
                out["txf"] = {"ok": True, "last": fq.last,
                              "chg": (fq.last - fq.prev_close) if fq.prev_close else None,
                              "pct": ((fq.last / fq.prev_close - 1) * 100) if fq.prev_close else None,
                              "ts": fq.ts.strftime("%m-%d %H:%M") if fq.ts else "", "status": "盤中",
                              "name": "台指期日盤"}
                raise StopIteration
        n = txf_night_payload()
        if n.get("ok") and n.get("last") is not None:
            live = in_txf_night()
            out["txf"] = {"ok": True, "last": n["last"], "chg": n.get("chg"), "pct": n.get("chg_pct"),
                          "ts": n.get("asof") or "", "status": "盤中" if live else "收盤",
                          "name": f"台指期夜盤 {n.get('month', '')}"}
        else:
            out["txf"] = {"ok": False, "reason": n.get("reason") or n.get("note") or "沒有夜盤資料"}
    except StopIteration:
        pass
    except Exception as exc:  # noqa: BLE001
        out["txf"] = {"ok": False, "reason": f"夜盤報價失敗：{type(exc).__name__}"}
    out["updated"] = now_taipei().strftime("%H:%M:%S")
    TICKER.update(out)


def _ticker_loop() -> None:
    while True:
        try:
            _ticker_once()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(30)


@app.on_event("startup")
def _start_ticker() -> None:
    threading.Thread(target=_ticker_loop, daemon=True, name="ticker").start()
    threading.Thread(target=_bench_refresh, daemon=True, name="bench").start()


BENCH: dict = {"t": 0.0, "data": [], "reason": "載入中"}


def _bench_refresh() -> None:
    try:
        import yfinance as yf
        from quotes import _yf_silent
        with _yf_silent():
            df = yf.download("^TWII", period="2y", interval="1d", progress=False, auto_adjust=False)
        if df is None or df.empty:
            BENCH.update(t=time.time(), reason="Yahoo 沒有回加權指數日線")
            return
        col = df["Close"]
        if hasattr(col, "columns"):
            col = col.iloc[:, 0]
        BENCH.update(t=time.time(), reason="", data=[{"date": d.strftime("%Y-%m-%d"), "close": round(float(v), 2)}
                                                     for d, v in col.dropna().items()])
    except Exception as exc:  # noqa: BLE001
        BENCH.update(t=time.time(), reason=f"加權指數日線失敗：{type(exc).__name__}")


@app.get("/api/bench")
def api_bench() -> JSONResponse:
    if time.time() - BENCH["t"] > 3600:
        threading.Thread(target=_bench_refresh, daemon=True).start()  # 背景更新，不阻塞
    return JSONResponse({"data": BENCH["data"], "reason": BENCH["reason"]})


@app.get("/api/ticker")
def api_ticker() -> JSONResponse:
    return JSONResponse(TICKER)


def _json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _csv(p: Path) -> list[dict]:
    try:
        with p.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def _f(x, d=None):
    try:
        v = float(x)
        return v if v == v else d
    except (TypeError, ValueError):
        return d


def _names() -> dict:
    n = _json(NAMES_FILE)
    t = nn_strategy.latest_target()
    for r in (t[1] if t else []):
        n.setdefault(r["code"], str(r.get("name", "")).split(" ", 1)[-1])
    return n


def account() -> dict:
    a = _json(PAPER / "account.json")
    eq = _f(a.get("equity"), 0) or 0
    pos = []
    for p in a.get("positions", []):
        last = _f(p.get("last"), p["avg_price"])
        mv = last * p["shares"]
        cost = p["avg_price"] * p["shares"]
        pos.append({"code": p["ticker"], "name": stock_names.label(p["ticker"]), "shares": p["shares"],
                    "avg": p["avg_price"], "last": last, "mv": mv, "weight": mv / eq if eq else 0,
                    "pnl": mv - cost, "pnl_pct": (mv / cost - 1) if cost else 0,
                    "nn_rank": p.get("nn_rank"), "industry": p.get("industry", "")})
    curve = {}
    for r in _csv(PAPER / "equity.csv"):
        curve[r["date"][:10]] = _f(r.get("equity"))
    init = _f(a.get("initial_cash"), 0) or 0
    return {"equity": eq, "cash": a.get("cash"), "initial": init, "pnl": eq - init,
            "as_of": a.get("last_session"), "target_month": a.get("last_target"),
            "positions": sorted(pos, key=lambda x: -x["mv"]),
            "curve": [{"date": k, "equity": v} for k, v in sorted(curve.items())]}


def research(n: int = 20) -> dict:
    rows = nn_strategy.preds_all()
    rows.sort(key=lambda r: int(float(r["rank"])))
    names = _names()
    top = [{"rank": int(float(r["rank"])), "code": r["code"], "name": stock_names.label(r["code"]),
            "pred": _f(r["pred_excess_ret"]), "n": int(float(r["n_stocks"]))} for r in rows[:n]]
    return {"mon": rows[0]["mon"] if rows else None, "rows": top,
            "note": "研究名單：模型預測下月超額報酬最高的股票，不是買進訊號"}


def monitor() -> dict:
    m = _csv(nn_strategy.NN_OUT / "monitor.csv")
    pts = [{"mon": r.get("") or r.get("mon"), "ic": _f(r.get("IC")), "ic12": _f(r.get("IC_roll12")),
            "hit12": _f(r.get("hit_roll12"))} for r in m]
    ic = _csv(nn_strategy.NN_OUT / "ic_monthly.csv")
    ics = [_f(r.get("IC_all")) for r in ic if _f(r.get("IC_all")) is not None]
    last = pts[-1] if pts else {}
    return {"series": pts, "latest": last, "ic_mean_all": sum(ics) / len(ics) if ics else None,
            "ic_pos_share": sum(x > 0 for x in ics) / len(ics) if ics else None, "n_months": len(ics),
            "neg_streak": int(_f(m[-1].get("IC_neg_streak"), 0)) if m else 0}


def news() -> dict:
    n = _json(PAPER / "coach_news.json")
    return {"as_of": n.get("as_of"), "count": n.get("news_count"),
            "keywords": (n.get("hot_keywords") or [])[:10], "stocks": (n.get("hot_stocks") or [])[:10],
            "held": (n.get("held_mentions") or [])[:10], "headlines": (n.get("headlines") or [])[:15],
            "note": "只顯示，不影響持股或下單"}


def coach_up() -> bool:
    for path in ("/api/health", "/"):
        try:
            with urllib.request.urlopen("http://127.0.0.1:7870" + path, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
    return False


@app.get("/")
def index():
    from fastapi.responses import HTMLResponse
    v = str(int(max((WEB / f).stat().st_mtime for f in ("app.js", "chat.js", "site.css", "app.css"))))
    return HTMLResponse((WEB / "index.html").read_text(encoding="utf-8").replace("{{v}}", v))


@app.get("/api/state")
def api_state() -> JSONResponse:
    wl = nn_strategy.watchlist()
    for r in wl.get("records") or []:
        r["label"] = stock_names.label(r.get("code"))
    return JSONResponse({"account": account(), "watchlist": wl,
                         "research": research(), "monitor": monitor(), "news": news(), "sim": _json(PAPER / "sim_status.json"),
                         "strategy": nn_strategy.STRATEGY})


@app.get("/api/coach/status")
def api_coach() -> JSONResponse:
    return JSONResponse({"up": coach_up(), "url": COACH_URL,
                         "hint": r"教練未啟動，執行 D:\trade-coach\run.ps1"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("webapp:app", host="127.0.0.1", port=8501, reload=False)


# ---- 永豐模擬帳戶：背景執行緒呼叫 sim_trader.py --snapshot（唯讀、只准 simulation），/api/sim 只讀快取檔 ----
import subprocess  # noqa: E402
from datetime import datetime as _dt  # noqa: E402

SIM_SNAP = PAPER / "sim_snapshot.json"


def _sim_market_hours(now=None) -> bool:
    n = now or _dt.now()
    return n.weekday() < 5 and (9, 0) <= (n.hour, n.minute) <= (13, 40)


def _sim_refresh_loop() -> None:
    while True:
        try:
            age = time.time() - SIM_SNAP.stat().st_mtime if SIM_SNAP.exists() else 1e9
            limit = 300 if _sim_market_hours() else 3600
            if age > limit and not (PAPER / "SIM_STOP").exists():
                subprocess.run([sys.executable, str(ROOT / "sim_trader.py"), "--snapshot"], cwd=str(ROOT),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception:
            pass
        time.sleep(60)


threading.Thread(target=_sim_refresh_loop, daemon=True, name="sim-snap").start()


def _sim_lab(code) -> str:
    try:
        return stock_names.label(code)
    except Exception:
        return str(code)


@app.get("/api/sim")
def api_sim() -> JSONResponse:
    snap = _json(SIM_SNAP)
    state = _json(PAPER / "sim_state.json")
    status = _json(PAPER / "sim_status.json")
    legacy = set(snap.get("legacy_codes") or [])
    for p in snap.get("positions") or []:
        p["label"] = _sim_lab(p["code"]); p["legacy"] = p["code"] in legacy
    for t in snap.get("trades") or []:
        t["label"] = _sim_lab(t["code"])
    mon = _dt.now().strftime("%Y-%m")
    logs = sorted(PAPER.glob("sim_orders_*.csv"))
    rows = _csv(logs[-1]) if logs else []
    for r in rows:
        r["label"] = _sim_lab(r.get("code"))
    recs = sorted(PAPER.glob("sim_reconcile_*.csv"))
    rec = _csv(recs[-1]) if recs else []
    for r in rec:
        r["label"] = _sim_lab(r.get("code"))
    compare, cmp_mon = [], None
    try:
        from nn_strategy import latest_target
        from sim_trader import BUDGET_NTD
        lt = latest_target()
        held = {p["code"]: p for p in (snap.get("positions") or [])}
        tg = {}
        if lt:
            cmp_mon = lt[0]
            for r in lt[1]:
                hp = held.get(r["code"]) or {}
                last = float(hp.get("last") or 0) or float(r.get("close") or 0)
                tg[r["code"]] = (r, int(r["weight"] * BUDGET_NTD // last) if last > 0 else 0)
        for c in list(tg) + [c for c in held if c not in tg]:
            r, t = tg.get(c, ({}, 0))
            a = int(float((held.get(c) or {}).get("shares") or 0))
            d = a - t
            if c in legacy and c not in tg:
                stt = "舊持股、待清倉"
            elif c not in tg:
                stt = "不在目標、應賣出"
            elif a == 0:
                stt = "未買進"
            elif t and abs(d) <= max(1, 0.1 * t):
                stt = "符合"
            else:
                stt = "多買" if d > 0 else "不足"
            compare.append({"code": c, "label": _sim_lab(c), "weight": r.get("weight"), "target_shares": t,
                            "sim_shares": a, "diff": d, "status": stt})
    except Exception as e:  # noqa: BLE001
        compare = [{"code": "", "label": f"對照計算失敗：{e}", "target_shares": None, "sim_shares": None, "diff": None, "status": ""}]
    return JSONResponse({"snapshot": snap, "state": state, "status": status, "log": rows[-60:],
                         "compare": compare, "compare_mon": cmp_mon,
                         "log_file": logs[-1].name if logs else None, "reconcile": rec,
                         "reconcile_file": recs[-1].name if recs else None, "month": mon})
