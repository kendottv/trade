r"""NN 紙上帳戶（全新，從頭算）。不是券商，沒有任何下單路徑。

用法（在 snr_backtest 下，用 .venv）：
  python nn_paper.py --init       建新帳戶，並以最新目標持股做第一次調倉（最新收盤價）
  python nn_paper.py --daily      每日：市值重估；trade_NN/out 出現新月份目標檔就調倉
  python nn_paper.py --status     印出帳戶
帳戶寫在 snr_backtest/paper_nn/（舊的 paper\ 完全不動）。
規格 v3 AC-13：費用計算全部改走 broker.py（最低手續費 NT$20）。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from config import INITIAL_CAPITAL  # noqa: E402
from nn_strategy import STRATEGY, latest_target  # noqa: E402
import stock_names  # noqa: E402
import proc_lock  # noqa: E402
from broker import commission_on, sell_fill, buy_cost  # AC-13

try:
    import quotes  # noqa: E402
except ImportError:
    quotes = None

PAPER = ROOT / "paper_nn"
TZ = timezone(timedelta(hours=8))
LEDGER_COLS = ["date", "ticker", "action", "reason", "price", "shares", "cash", "equity", "snr"]
EQUITY_COLS = ["date", "cash", "market_value", "equity"]
LIVE_ORDERS_ENABLED = False
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
DAILY_LOCK = PAPER / "daily.lock"


def now() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S%z")


def load() -> dict:
    p = PAPER / "account.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save(acct: dict) -> None:
    PAPER.mkdir(exist_ok=True)
    acct["updated_at"] = now()
    (PAPER / "account.json").write_text(json.dumps(acct, ensure_ascii=False, indent=2), encoding="utf-8")


def _append(name: str, cols: list[str], rows: list[dict]) -> None:
    p = PAPER / name
    if name == "equity.csv" and p.exists():
        days = {x["date"] for x in rows}
        with p.open(encoding="utf-8") as f:
            old = [r for r in csv.DictReader(f) if r["date"] not in days]
        with p.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(old + rows)
        return
    new = not p.exists()
    with p.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def log(text: str) -> None:
    with (PAPER / "daily_log.md").open("a", encoding="utf-8") as f:
        f.write(text.rstrip() + "\n\n")


def _shioaji_src(ts) -> str:
    if ts is None:
        return datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    if hasattr(ts, "strftime"):
        try:
            return ts.strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
    return str(ts)[:16]


def _pure_date(src: str) -> str | None:
    m = _DATE_RE.search(src or "")
    return m.group(1) if m else None


def _session_day(live: dict[str, tuple[float, str]]) -> str:
    dates = [d for v in live.values() if (d := _pure_date(v[1]))]
    if dates:
        return max(dates)
    return datetime.now(TZ).strftime("%Y-%m-%d")


def get_shioaji_last(tickers: list[str]) -> dict[str, tuple[float, str]]:
    out: dict[str, tuple[float, str]] = {}
    if not quotes or not tickers:
        return out
    try:
        feed = quotes.get_feed()
        if getattr(feed, "name", "") != "shioaji":
            return out
        for t in tickers:
            q = feed.last(t)
            if q is not None and q.last and q.last > 0:
                src = f"shioaji {_shioaji_src(q.ts)}"
                out[t] = (float(q.last), src)
    except Exception:
        pass
    return out


def fetch_closes(codes: list[str]) -> dict[str, tuple[float, str]]:
    out: dict[str, tuple[float, str]] = {}
    if not codes:
        return out
    sj = get_shioaji_last(codes)
    out.update(sj)
    missing = [c for c in codes if c not in out]
    if not missing:
        return out
    try:
        import yfinance as yf
    except ImportError:
        return out
    for suf in (".TW", ".TWO"):
        need = [c for c in missing if c not in out]
        if not need:
            break
        try:
            df = yf.download([c + suf for c in need], period="10d", progress=False,
                             auto_adjust=False, group_by="ticker", threads=True)
        except Exception:
            continue
        for c in need:
            try:
                s = (df[c + suf]["Close"] if len(need) > 1 else df["Close"]).dropna()
                if hasattr(s, "columns"):
                    s = s.iloc[:, 0]
                if len(s):
                    day = str(s.index[-1])[:10]
                    out[c] = (float(s.iloc[-1]), f"yahoo {day}")
            except Exception:
                pass
    return out


def _equity(acct: dict, px: dict[str, float]) -> tuple[float, float]:
    mv = sum(p["shares"] * px.get(p["ticker"], p.get("last", p["avg_price"])) for p in acct["positions"])
    return mv, acct["cash"] + mv


def rebalance(acct: dict, mon: str, rows: list[dict]) -> list[dict]:
    assert not LIVE_ORDERS_ENABLED
    s = STRATEGY
    codes = sorted({r["code"] for r in rows} | {p["ticker"] for p in acct["positions"]})
    live = fetch_closes(codes)
    px, src = {}, {}
    for r in rows:
        if r["code"] in live:
            px[r["code"]], src[r["code"]] = live[r["code"]]
        else:
            px[r["code"]], src[r["code"]] = r["close"], f"{mon} 月底收盤(後備)"
    for p in acct["positions"]:
        if p["ticker"] not in px:
            v = live.get(p["ticker"])
            px[p["ticker"]] = v[0] if v else p.get("last", p["avg_price"])
            src[p["ticker"]] = v[1] if v else "前次價格"
    day = _session_day(live)
    _, eq = _equity(acct, px)
    want = {r["code"]: r for r in rows}
    try:
        stock_names.refresh_if_old(0 if mon != acct.get("last_target") else 7)
    except Exception:
        pass
    for p in acct["positions"]:
        p["name"] = stock_names.label(p["ticker"])
    led = []
    # 先賣（改用 broker.sell_fill，含最低 NT$20）
    for p in list(acct["positions"]):
        tgt = int(eq * want[p["ticker"]]["weight"] / px[p["ticker"]]) if p["ticker"] in want else 0
        if p["shares"] > tgt:
            q = p["shares"] - tgt
            fill_price = px[p["ticker"]] * (1 - s["slippage"])
            sf = sell_fill(q, fill_price, 0.001425, 20.0, 0.003)
            acct["cash"] += sf.cash_delta
            p["shares"] -= q
            led.append({"date": day, "ticker": p["ticker"], "action": "SELL", "reason": f"NN 調倉 {mon}",
                        "price": round(fill_price, 4), "shares": q})
    acct["positions"] = [p for p in acct["positions"] if p["shares"] > 0]
    # 再買（改用 broker.buy_cost，含最低 NT$20）
    for code, r in want.items():
        cur = next((p for p in acct["positions"] if p["ticker"] == code), None)
        have = cur["shares"] if cur else 0
        fill_price = px[code] * (1 + s["slippage"])
        tgt = int(eq * r["weight"] / (fill_price * (1 + s["buy_fee"])))
        q = min(tgt - have, int(acct["cash"] / (fill_price * (1 + s["buy_fee"]))))
        if q <= 0:
            continue
        cost = buy_cost(q, fill_price, 0.001425, 20.0)
        if cost > acct["cash"] + 1e-8:
            continue
        acct["cash"] -= cost
        if cur:
            cur["avg_price"] = (cur["avg_price"] * have + cost) / (have + q)
            cur["shares"] += q
        else:
            acct["positions"].append({"ticker": code, "name": stock_names.label(code), "shares": q,
                                      "avg_price": round(cost / q, 4), "entry_date": day,
                                      "entry_snr": None, "time_stop_count": 0, "trail_armed": False,
                                      "nn_rank": r["rank"], "nn_score": r["score"],
                                      "industry": r.get("industry", "")})
        led.append({"date": day, "ticker": code, "action": "BUY", "reason": f"NN 調倉 {mon}",
                    "price": round(fill_price, 4), "shares": q})
    for p in acct["positions"]:
        p["last"] = px[p["ticker"]]
        p["price_src"] = src.get(p["ticker"], "")
    mv, eq = _equity(acct, px)
    acct["equity"] = round(eq, 2)
    acct["cash"] = round(acct["cash"], 2)
    acct["last_session"] = day
    acct["last_target"] = mon
    for r in led:
        r["cash"], r["equity"] = acct["cash"], acct["equity"]
    _append("ledger.csv", LEDGER_COLS, led)
    _append("equity.csv", EQUITY_COLS, [{"date": day, "cash": acct["cash"], "market_value": round(mv, 2),
                                         "equity": acct["equity"]}])
    fb = [c for c in want if c not in live]
    log(f"## {day} NN 調倉（目標 {mon}）\n買 {sum(r['action']=='BUY' for r in led)} 筆、賣 "
        f"{sum(r['action']=='SELL' for r in led)} 筆；權益 {acct['equity']:,.0f}，現金 {acct['cash']:,.0f}。"
        + (f"\n抓不到最新收盤、改用月底收盤：{', '.join(fb)}" if fb else ""))
    return led


def init(reset: bool = False) -> dict:
    if (PAPER / "account.json").exists() and not reset:
        raise SystemExit("paper_nn\\account.json 已存在；要重來請加 --reset")
    PAPER.mkdir(exist_ok=True)
    for n in ("account.json", "ledger.csv", "equity.csv", "daily_log.md"):
        (PAPER / n).unlink(missing_ok=True)
    acct = {"cash": INITIAL_CAPITAL, "equity": INITIAL_CAPITAL, "initial_cash": INITIAL_CAPITAL,
            "positions": [], "pending": [], "strategy": STRATEGY["name"], "created_at": now(),
            "last_session": None, "last_target": None, "paper_only": True}
    (PAPER / "daily_log.md").write_text(f"# NN 紙上帳戶\n\n建立 {now()}，初始資金 {INITIAL_CAPITAL:,.0f}"
                                        f"（trade config.INITIAL_CAPITAL）。只模擬，不下單。\n\n",
                                        encoding="utf-8")
    t = latest_target()
    if t:
        rebalance(acct, *t)
    save(acct)
    return acct


def daily() -> dict:
    deadline = time.time() + 600
    while not proc_lock.acquire(DAILY_LOCK):
        if time.time() >= deadline:
            raise SystemExit("無法取得 daily.lock（超過 10 分鐘），放棄本次執行")
        time.sleep(5)
    acct = load() or init()
    t = latest_target()
    if t and t[0] != acct.get("last_target"):
        rebalance(acct, *t)
    else:
        live = fetch_closes([p["ticker"] for p in acct["positions"]])
        for p in acct["positions"]:
            if p["ticker"] in live:
                p["last"], p["price_src"] = live[p["ticker"]]
        day = _session_day(live)
        mv, eq = _equity(acct, {})
        acct["equity"], acct["last_session"] = round(eq, 2), day
        _append("equity.csv", EQUITY_COLS, [{"date": day, "cash": acct["cash"], "market_value": round(mv, 2),
                                             "equity": acct["equity"]}])
    save(acct)
    return acct


def status() -> None:
    a = load()
    if not a:
        print("尚未建立；先跑 --init")
        return
    print(f"權益 {a['equity']:,.0f}  現金 {a['cash']:,.0f}  持股 {len(a['positions'])} 檔  "
          f"日期 {a['last_session']}  目標 {a['last_target']}")
    for p in a["positions"]:
        print(f"  {p['name']:<10} {p['shares']:>6} 股  成本 {p['avg_price']:>9.2f}  現價 {p.get('last', 0):>9.2f}  {p.get('price_src', '')}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--daily", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.init:
        init(a.reset)
    elif a.daily:
        daily()
    status()
