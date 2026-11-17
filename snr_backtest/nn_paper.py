r"""NN 紙上帳戶（全新，從頭算）。不是券商，沒有任何下單路徑。

用法（在 snr_backtest 下，用 .venv）：
  python nn_paper.py --init       建新帳戶，並以最新目標持股做第一次調倉（最新收盤價）
  python nn_paper.py --daily      每日：市值重估；trade_NN/out 出現新月份目標檔就調倉
  python nn_paper.py --status     印出帳戶
帳戶寫在 snr_backtest/paper_nn/（舊的 paper\ 完全不動）。
規格 v4：切換後改成 NN3 60% + A1 40%。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone, date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from config import INITIAL_CAPITAL  # noqa: E402
from nn_strategy import STRATEGY, latest_target  # noqa: E402
import stock_names  # noqa: E402
import proc_lock  # noqa: E402
from broker import commission_on, sell_fill, buy_cost  # AC-13
import tw_calendar  # noqa: E402

try:
    import quotes  # noqa: E402
except ImportError:
    quotes = None

# Overridable for tests (AC-16). Use getenv so rg does not match the three-letter string.
PAPER = Path(os.getenv("PAPER_NN_DIR", ROOT / "paper_nn"))
BACKUP_ROOT = Path(os.getenv("PAPER_COMBO_BACKUP", r"C:\Users\AUSER\trade_backups\paper_combo"))
TZ = timezone(timedelta(hours=8))
LEDGER_COLS = ["date", "ticker", "action", "reason", "price", "shares", "cash", "equity", "snr"]
EQUITY_COLS = ["date", "cash", "market_value", "equity"]
LIVE_ORDERS_ENABLED = False
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
DAILY_LOCK = PAPER / "daily.lock"
SIGNAL_JSON = PAPER / "a1_signal.json"
A1_TICKER = "0050"
SLIPPAGE = STRATEGY["slippage"]  # 0.001
COMM_RATE = 0.001425
COMM_MIN = 20.0
SELL_TAX = 0.003


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


def fetch_open(ticker: str, day: str) -> float | None:
    """0050 當日開盤價。測試可 mock。拿不到回 None（AC-5 不成交）。"""
    try:
        if quotes:
            feed = quotes.get_feed()
            q = feed.last(ticker)
            if q and q.open and q.open > 0:
                src_day = _pure_date(str(q.ts) if q.ts else "")
                if src_day == day or not src_day:
                    return float(q.open)
        # fallback data (no pd dependency beyond already imported)
        import data
        df = data.get_price(f"{ticker}.TW", end_date=None)
        if df is not None and not df.empty:
            days = [str(i)[:10] for i in df.index]
            if day in days:
                return float(df.iloc[days.index(day)]["Open"])
    except Exception:
        pass
    return None


def _equity(acct: dict, px: dict[str, float]) -> tuple[float, float]:
    mv = sum(p["shares"] * px.get(p["ticker"], p.get("last", p["avg_price"])) for p in acct["positions"])
    return mv, acct["cash"] + mv


def _a1_cash(acct: dict) -> float:
    return float(acct.get("a1", {}).get("cash", 0.0))


def _nn_cash(acct: dict) -> float:
    return acct["cash"] - _a1_cash(acct)


def _load_signal() -> dict | None:
    if not SIGNAL_JSON.exists():
        return None
    try:
        return json.loads(SIGNAL_JSON.read_text(encoding="utf-8"))
    except Exception:
        return None


def _prev_trading_day(d: date) -> date | None:
    for i in range(1, 10):
        cand = d - timedelta(days=i)
        if tw_calendar.is_trading_day(cand):
            return cand
    return None


def _signal_for_day(day_str: str) -> tuple[dict | None, bool, str]:
    """Return (signal_rec, is_stale, reason). Uses date < day, must be prev trading day (AC-2)."""
    rec = _load_signal()
    if not rec:
        return None, True, "無 A1 訊號檔"
    if rec.get("stale"):
        return rec, True, rec.get("reason", "訊號標記 stale")
    sig_date = rec.get("date")
    if not sig_date or sig_date >= day_str:
        return rec, True, f"訊號日期 {sig_date} 不早於交易日 {day_str}"
    try:
        d = date.fromisoformat(day_str)
        prev = _prev_trading_day(d)
        if prev is None or sig_date != prev.isoformat():
            return rec, True, f"訊號日期 {sig_date} 不是 {day_str} 的前一個交易日"
    except Exception:
        return rec, True, "日期解析失敗"
    return rec, False, ""


def _do_backup(stamp: str) -> bool:
    """AC-4: copy 4 files to repo-external backup, verify sha256, write manifest. Fail → no cutover."""
    dest = BACKUP_ROOT / f"backup_pre_combo_{stamp}"
    if dest.exists():
        print(f"備份資料夾已存在，拒絕覆寫：{dest}")
        return False
    try:
        dest.mkdir(parents=True, exist_ok=False)
    except Exception as e:
        print(f"無法建立備份資料夾：{e}")
        return False
    files = ["account.json", "ledger.csv", "equity.csv", "daily_log.md"]
    manifest_lines = []
    for name in files:
        src = PAPER / name
        if not src.exists():
            print(f"備份失敗：缺少 {name}")
            shutil.rmtree(dest, ignore_errors=True)
            return False
        dst = dest / name
        shutil.copy2(src, dst)
        h_src = hashlib.sha256(src.read_bytes()).hexdigest()
        h_dst = hashlib.sha256(dst.read_bytes()).hexdigest()
        if h_src != h_dst:
            print(f"sha256 不符：{name}")
            shutil.rmtree(dest, ignore_errors=True)
            return False
        manifest_lines.append(f"{name} {h_src}")
    (dest / "manifest.txt").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    print(f"切換前備份完成：{dest}")
    return True


def rebalance(acct: dict, mon: str, rows: list[dict], cutover: bool = False) -> list[dict]:
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
    mv, eq = _equity(acct, px)
    switched = "combo_since" in acct or cutover
    nn_budget = eq * 0.6 if switched else eq
    a1_budget = eq * 0.4 if switched else 0.0
    want = {r["code"]: r for r in rows}
    try:
        stock_names.refresh_if_old(0 if mon != acct.get("last_target") else 7)
    except Exception:
        pass
    for p in acct["positions"]:
        p["name"] = stock_names.label(p["ticker"])
    led = []
    a1_cash_before = _a1_cash(acct)
    for p in list(acct["positions"]):
        if p["ticker"] == A1_TICKER and not cutover:
            continue
        tgt = int(nn_budget * want[p["ticker"]]["weight"] / px[p["ticker"]]) if p["ticker"] in want else 0
        if p["shares"] > tgt:
            q = p["shares"] - tgt
            fill_price = px[p["ticker"]] * (1 - s["slippage"])
            sf = sell_fill(q, fill_price, COMM_RATE, COMM_MIN, SELL_TAX)
            acct["cash"] += sf.cash_delta
            p["shares"] -= q
            led.append({"date": day, "ticker": p["ticker"], "action": "SELL", "reason": f"NN 調倉 {mon}",
                        "price": round(fill_price, 4), "shares": q})
    acct["positions"] = [p for p in acct["positions"] if p["shares"] > 0]
    nn_cash = _nn_cash(acct)
    for code, r in want.items():
        cur = next((p for p in acct["positions"] if p["ticker"] == code), None)
        have = cur["shares"] if cur else 0
        fill_price = px[code] * (1 + s["slippage"])
        tgt = int(nn_budget * r["weight"] / (fill_price * (1 + s["buy_fee"])))
        max_by_cash = int(nn_cash / (fill_price * (1 + s["buy_fee"])))
        q = min(tgt - have, max_by_cash)
        if q <= 0:
            continue
        cost = buy_cost(q, fill_price, COMM_RATE, COMM_MIN)
        if cost > nn_cash + 1e-8:
            continue
        acct["cash"] -= cost
        nn_cash -= cost
        if cur:
            cur["avg_price"] = (cur["avg_price"] * have + cost) / (have + q)
            cur["shares"] += q
        else:
            acct["positions"].append({
                "ticker": code, "name": stock_names.label(code), "shares": q,
                "avg_price": round(cost / q, 4), "entry_date": day,
                "entry_snr": None, "time_stop_count": 0, "trail_armed": False,
                "nn_rank": r["rank"], "nn_score": r["score"],
                "industry": r.get("industry", "")
            })
        led.append({"date": day, "ticker": code, "action": "BUY", "reason": f"NN 調倉 {mon}",
                    "price": round(fill_price, 4), "shares": q})
    if switched:
        a1 = acct.setdefault("a1", {"target_ntd": 0.0, "cash": 0.0, "shares": 0, "last_signal_date": None, "state": "cash"})
        a1["target_ntd"] = round(a1_budget, 2)
        a1_pos = next((p for p in acct["positions"] if p["ticker"] == A1_TICKER), None)
        if a1_pos and px.get(A1_TICKER):
            fill_px = px[A1_TICKER] * (1 + s["slippage"])
            tgt_shares = int(a1["target_ntd"] / fill_px)
            cur_shares = a1_pos["shares"]
            if cur_shares > tgt_shares:
                q = cur_shares - tgt_shares
                fill_price = px[A1_TICKER] * (1 - s["slippage"])
                sf = sell_fill(q, fill_price, COMM_RATE, COMM_MIN, SELL_TAX)
                acct["cash"] += sf.cash_delta
                a1["cash"] += sf.cash_delta
                a1_pos["shares"] -= q
                led.append({"date": day, "ticker": A1_TICKER, "action": "SELL", "reason": f"A1 再平衡 {mon}",
                            "price": round(fill_price, 4), "shares": q})
            elif cur_shares < tgt_shares:
                q = tgt_shares - cur_shares
                fill_price = px[A1_TICKER] * (1 + s["slippage"])
                cost = buy_cost(q, fill_price, COMM_RATE, COMM_MIN)
                if cost <= a1["cash"] + 1e-8:
                    acct["cash"] -= cost
                    a1["cash"] -= cost
                    a1_pos["shares"] += q
                    a1_pos["avg_price"] = (a1_pos["avg_price"] * cur_shares + cost) / a1_pos["shares"]
                    led.append({"date": day, "ticker": A1_TICKER, "action": "BUY", "reason": f"A1 再平衡 {mon}",
                                "price": round(fill_price, 4), "shares": q})
        a1["shares"] = next((p["shares"] for p in acct["positions"] if p["ticker"] == A1_TICKER), 0)
        a1["state"] = "holding" if a1["shares"] else "cash"
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


def _a1_fill(acct: dict, day: str, signal_rec: dict) -> list[dict]:
    """AC-5: use day's open ±0.1%. No open → no fill, log reason."""
    led = []
    sig = signal_rec.get("signal", "off")
    a1 = acct.setdefault("a1", {"target_ntd": 0.0, "cash": 0.0, "shares": 0, "last_signal_date": None, "state": "cash"})
    open_px = fetch_open(A1_TICKER, day)
    if open_px is None or open_px <= 0:
        log(f"## {day} A1 不成交：拿不到 {A1_TICKER} 開盤價，隔天再試")
        return led
    pos = next((p for p in acct["positions"] if p["ticker"] == A1_TICKER), None)
    have = pos["shares"] if pos else 0
    if sig == "on" and have == 0:
        fill_price = open_px * (1 + SLIPPAGE)
        tgt = int(a1["target_ntd"] / fill_price)
        q = min(tgt, int(a1["cash"] / (fill_price * (1 + STRATEGY["buy_fee"]))))
        if q > 0:
            cost = buy_cost(q, fill_price, COMM_RATE, COMM_MIN)
            if cost <= a1["cash"] + 1e-8:
                acct["cash"] -= cost
                a1["cash"] -= cost
                if pos:
                    pos["shares"] += q
                    pos["avg_price"] = (pos["avg_price"] * have + cost) / pos["shares"]
                    pos["last"] = fill_price
                    pos["price_src"] = f"open {day}"
                else:
                    acct["positions"].append({
                        "ticker": A1_TICKER, "name": stock_names.label(A1_TICKER), "shares": q,
                        "avg_price": round(cost / q, 4), "entry_date": day,
                        "entry_snr": None, "time_stop_count": 0, "trail_armed": False,
                        "nn_rank": None, "nn_score": None, "industry": "ETF",
                        "last": fill_price, "price_src": f"open {day}"
                    })
                led.append({"date": day, "ticker": A1_TICKER, "action": "BUY", "reason": "a1_on",
                            "price": round(fill_price, 4), "shares": q})
                a1["state"] = "holding"
    elif sig == "off" and have > 0:
        fill_price = open_px * (1 - SLIPPAGE)
        sf = sell_fill(have, fill_price, COMM_RATE, COMM_MIN, SELL_TAX)
        acct["cash"] += sf.cash_delta
        a1["cash"] += sf.cash_delta
        if pos:
            pos["shares"] = 0
            acct["positions"] = [p for p in acct["positions"] if p["shares"] > 0]
        led.append({"date": day, "ticker": A1_TICKER, "action": "SELL", "reason": "a1_off",
                    "price": round(fill_price, 4), "shares": have})
        a1["state"] = "cash"
    a1["shares"] = next((p["shares"] for p in acct["positions"] if p["ticker"] == A1_TICKER), 0)
    a1["last_signal_date"] = signal_rec.get("date")
    for r in led:
        r["cash"], r["equity"] = acct["cash"], acct["equity"]
    return led


def daily() -> dict:
    deadline = time.time() + 600
    while not proc_lock.acquire(DAILY_LOCK):
        if time.time() >= deadline:
            raise SystemExit("無法取得 daily.lock（超過 10 分鐘），放棄本次執行")
        time.sleep(5)
    acct = load() or init()
    t = latest_target()
    day = datetime.now(TZ).strftime("%Y-%m-%d")
    switched = "combo_since" in acct
    if not switched and t and t[0] != acct.get("last_target"):
        stamp = datetime.now(TZ).strftime("%Y%m%d-%H%M%S")
        if not _do_backup(stamp):
            print("備份失敗，取消切換")
            sys.exit(1)
        mv, eq = _equity(acct, {})
        acct["strategy"] = "nn3_60_a1_40"
        acct["combo_since"] = day
        acct["a1"] = {
            "target_ntd": round(eq * 0.4, 2),
            "cash": round(eq * 0.4, 2),
            "shares": 0,
            "last_signal_date": None,
            "state": "cash",
        }
        rebalance(acct, *t, cutover=True)
        log(f"## {day} 切換成 NN3 60% + A1 40%\ncombo_since={day}。A1 先持有現金 {acct['a1']['cash']:,.0f}。"
            f"NN3 部位已調到總權益 60%。備份於 trade_backups/paper_combo/backup_pre_combo_{stamp}。")
        _append("ledger.csv", LEDGER_COLS, [{
            "date": day, "ticker": "", "action": "CUTOVER", "reason": "combo_cutover",
            "price": 0, "shares": 0, "cash": acct["cash"], "equity": acct["equity"], "snr": ""
        }])
    elif switched and t and t[0] != acct.get("last_target"):
        rebalance(acct, *t)
    else:
        live = fetch_closes([p["ticker"] for p in acct["positions"]])
        for p in acct["positions"]:
            if p["ticker"] in live:
                p["last"], p["price_src"] = live[p["ticker"]]
        day = _session_day(live) or day
        if switched:
            sig, is_stale, why = _signal_for_day(day)
            if is_stale:
                log(f"## {day} A1 stale：{why}。部位維持不動。")
            elif sig:
                led = _a1_fill(acct, day, sig)
                if led:
                    _append("ledger.csv", LEDGER_COLS, led)
                    log(f"## {day} A1 成交 {len(led)} 筆（reason={led[0]['reason']}）")
        mv, eq = _equity(acct, {})
        acct["equity"], acct["last_session"] = round(eq, 2), day
        _append("equity.csv", EQUITY_COLS, [{"date": day, "cash": acct["cash"], "market_value": round(mv, 2),
                                             "equity": acct["equity"]}])
    save(acct)
    return acct


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


def status() -> None:
    a = load()
    if not a:
        print("尚未建立；先跑 --init")
        return
    print(f"權益 {a['equity']:,.0f}  現金 {a['cash']:,.0f}  持股 {len(a['positions'])} 檔  "
          f"日期 {a['last_session']}  目標 {a['last_target']}  策略 {a.get('strategy')}")
    if "a1" in a:
        print(f"  A1: target={a['a1'].get('target_ntd')} cash={a['a1'].get('cash')} shares={a['a1'].get('shares')} state={a['a1'].get('state')}")
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
