r"""NN 策略：永豐 Shioaji「模擬環境」自動送單。只准 simulation，沒有任何真單路徑。

用法（snr_backtest 下，用 .venv）：
  python sim_trader.py                 dry-run：算差額、印出委託，不登入下單（預設）
  python sim_trader.py --submit        送到「模擬」帳戶（先賣後買，零股/整股限價 ROD）
  python sim_trader.py --reconcile     收盤後對帳：成交回報 → sim_orders_YYYY-MM.csv、sim_reconcile_YYYY-MM.csv
  python sim_trader.py --auto open     排程用：每月第一個交易日送單；第二個交易日補單一次
  python sim_trader.py --auto close    排程用：送單/補單當天收盤後對帳
  python sim_trader.py --selftest      模擬環境小測：0050 買 1 股（遠低於市價）→ 立刻刪單
停止開關：paper_nn\SIM_STOP 存在就什麼都不做。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import traceback
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from nn_strategy import latest_target  # noqa: E402
from broker import tw_tick  # noqa: E402
import tw_calendar  # noqa: E402

PAPER = ROOT / "paper_nn"
STOP_FILE = PAPER / "SIM_STOP"
STATUS_FILE = PAPER / "sim_status.json"
STATE_FILE = PAPER / "sim_state.json"

# ---- 硬性規則（不要改；沒有任何旗標可以打開真單）----
SIMULATION_ONLY = True
TOTAL_MAX_NTD = 1_000_000      # 單次買進總額上限
PER_ORDER_MAX_NTD = 100_000    # 單筆上限
BUY_PAD = 0.005                # 買：ask/last +0.5%
SELL_PAD = 0.005               # 賣：bid/last −0.5%


class LiveTradingRefused(RuntimeError):
    pass


def now() -> datetime:
    return datetime.now()


def stamp() -> str:
    return now().strftime("%Y-%m-%d %H:%M:%S")


def write_status(**kw) -> None:
    PAPER.mkdir(exist_ok=True)
    old = {}
    if STATUS_FILE.exists():
        try:
            old = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            old = {}
    old.update(kw)
    old["updated"] = stamp()
    old["simulation_only"] = True
    STATUS_FILE.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(st: dict) -> None:
    STATE_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def check_stop() -> None:
    if STOP_FILE.exists():
        write_status(state="stopped", message="SIM_STOP 存在，已中止")
        raise SystemExit("SIM_STOP 存在，中止。")


# ---------------- login (simulation only) ----------------
_SIM_API_IDS: set[int] = set()  # 只有 login() 用 simulation=True 建的物件會登記在這裡


def assert_sim(api) -> None:
    if not SIMULATION_ONLY:
        raise LiveTradingRefused("SIMULATION_ONLY 被改掉，拒絕執行")
    if id(api) not in _SIM_API_IDS:
        raise LiveTradingRefused("Shioaji 物件不是本檔用 simulation=True 建立的，拒絕執行")


def login():
    import shioaji as sj
    import quotes  # 沿用既有讀金鑰路徑；本檔不讀、不印金鑰
    if not quotes._simulation_forced():
        raise LiveTradingRefused("broker_secrets 的 simulation 不是 true，拒絕執行")
    key, secret = quotes._shioaji_keys()
    if not key or not secret:
        raise RuntimeError("讀不到 Shioaji API Key（broker_secrets.json）")
    api = sj.Shioaji(simulation=True)  # 寫死，不接受參數
    _SIM_API_IDS.add(id(api))
    # 本檔從不呼叫 activate_ca（真單必須有憑證），雙重保險
    api.login(api_key=key, secret_key=secret)
    del key, secret
    assert_sim(api)
    return api


def safe_place(api, contract, order):
    """唯一的送單入口。每次都再檢查一次 simulation。"""
    assert_sim(api)
    return api.place_order(contract, order)


# ---------------- prices ----------------
def tick_round(px: float, up: bool) -> float:
    t = tw_tick(px)
    n = px / t
    n = math.ceil(n - 1e-9) if up else math.floor(n + 1e-9)
    return round(n * t, 2)


def snap_prices(api, codes: list[str]) -> dict:
    out = {}
    cons = [api.Contracts.Stocks[c] for c in codes if api.Contracts.Stocks[c] is not None]
    for i in range(0, len(cons), 200):
        for s in api.snapshots(cons[i:i + 200]):
            out[s.code] = {"close": float(s.close or 0), "ask": float(getattr(s, "sell_price", 0) or 0),
                           "bid": float(getattr(s, "buy_price", 0) or 0)}
    for c in cons:
        d = out.setdefault(c.code, {"close": 0, "ask": 0, "bid": 0})
        d["limit_up"] = float(c.limit_up or 0)
        d["limit_down"] = float(c.limit_down or 0)
        d["reference"] = float(c.reference or 0)
    return out


def file_prices(rows: list[dict]) -> dict:
    return {r["code"]: {"close": float(r.get("close") or 0), "ask": 0, "bid": 0,
                        "reference": float(r.get("close") or 0),
                        "limit_up": tick_round(float(r.get("close") or 0) * 1.1, False),
                        "limit_down": tick_round(float(r.get("close") or 0) * 0.9, True)} for r in rows}


# ---------------- plan ----------------
def positions(api) -> dict[str, int]:
    import shioaji as sj
    pos = api.list_positions(api.stock_account, unit=sj.constant.Unit.Share)
    return {p.code: int(p.quantity) for p in pos if int(p.quantity) != 0}


BUDGET_NTD = 980_000  # 目標用權重 × 98 萬換算股數（留 2% 給手續費/滑價）


def target_shares(target_rows: list[dict], px: dict) -> dict[str, int]:
    out = {}
    for r in target_rows:
        p = px.get(r["code"]) or {}
        last = p.get("ask") or p.get("close") or p.get("reference") or float(r.get("close") or 0)
        out[r["code"]] = int(float(r["weight"]) * BUDGET_NTD // last) if last > 0 else 0
    return out


def plan(target_rows: list[dict], held: dict[str, int], px: dict) -> tuple[list[dict], list[str]]:
    tgt = target_shares(target_rows, px)
    orders, notes = [], []
    for code in sorted(set(tgt) | set(held)):
        diff = tgt.get(code, 0) - held.get(code, 0)
        if diff == 0:
            continue
        p = px.get(code) or {}
        last = p.get("close") or p.get("reference") or 0
        if last <= 0:
            notes.append(f"{code} 沒有價格，跳過")
            continue
        if diff > 0:
            base = p.get("ask") or last
            if p.get("limit_up") and last >= p["limit_up"] - 1e-9:
                notes.append(f"{code} 漲停，不買")
                continue
            lim = tick_round(base * (1 + BUY_PAD), True)
            if p.get("limit_up"):
                lim = min(lim, p["limit_up"])
        else:
            base = p.get("bid") or last
            lim = tick_round(base * (1 - SELL_PAD), False)
            if p.get("limit_down"):
                lim = max(lim, p["limit_down"])
        side = "Buy" if diff > 0 else "Sell"
        qty = abs(diff)
        lots, odd = divmod(qty, 1000)
        if lots and side == "Sell":
            # 賣出（含舊持股清倉）拆成多筆，每筆 ≤ 單筆上限，整張走一般盤
            per = max(1, int(PER_ORDER_MAX_NTD // (lim * 1000)))
            if lim * 1000 > PER_ORDER_MAX_NTD:
                # 一張就超過上限：改用盤中零股分批，每筆 ≤ 上限且 ≤ 999 股
                sh = lots * 1000
                per_sh = min(999, int(PER_ORDER_MAX_NTD // lim))
                while sh:
                    n = min(per_sh, sh)
                    orders.append({"code": code, "side": side, "lot": "IntradayOdd", "qty": n, "shares": n, "price": lim,
                                   "legacy": code not in tgt})
                    sh -= n
                lots = 0
            while lots:
                n = min(per, lots)
                orders.append({"code": code, "side": side, "lot": "Common", "qty": n, "shares": n * 1000, "price": lim,
                               "legacy": code not in tgt})
                lots -= n
        elif lots:
            orders.append({"code": code, "side": side, "lot": "Common", "qty": lots, "shares": lots * 1000, "price": lim})
        if odd:
            orders.append({"code": code, "side": side, "lot": "IntradayOdd", "qty": odd, "shares": odd, "price": lim})
    # 風控
    kept, total = [], 0.0
    for o in sorted(orders, key=lambda o: o["side"] != "Sell"):  # 先賣後買
        amt = o["shares"] * o["price"]
        o["amount"] = round(amt)
        if amt > PER_ORDER_MAX_NTD:
            notes.append(f"{o['code']} {o['side']} {amt:,.0f} 超過單筆上限 {PER_ORDER_MAX_NTD:,}，跳過")
            continue
        if o["side"] == "Buy":
            if total + amt > TOTAL_MAX_NTD:
                notes.append(f"{o['code']} 買進會超過總額上限 {TOTAL_MAX_NTD:,}，跳過")
                continue
            total += amt
        kept.append(o)
    return kept, notes


def make_order(api, o):
    import shioaji as sj
    C = sj.constant
    return api.Order(price=o["price"], quantity=o["qty"],
                     action=C.Action.Buy if o["side"] == "Buy" else C.Action.Sell,
                     price_type=C.StockPriceType.LMT, order_type=C.OrderType.ROD,
                     order_lot=C.StockOrderLot.IntradayOdd if o["lot"] == "IntradayOdd" else C.StockOrderLot.Common,
                     account=api.stock_account)


ORDER_COLS = ["time", "mon", "kind", "code", "side", "lot", "qty", "shares", "price", "amount",
              "order_id", "status", "deal_shares", "deal_avg", "msg"]


def log_path(mon: str) -> Path:
    return PAPER / f"sim_orders_{mon}.csv"


def append_log(mon: str, rows: list[dict]) -> None:
    p = log_path(mon)
    new = not p.exists()
    with p.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ORDER_COLS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)


# ---------------- actions ----------------
def run(submit: bool, kind: str = "open") -> int:
    check_stop()
    t = latest_target()
    if not t:
        write_status(state="no_target", message="找不到 paper_target_*.csv")
        print("找不到目標檔"); return 1
    mon, rows = t
    api = None
    if submit:
        api = login()
        held = positions(api)
        px = snap_prices(api, sorted({r["code"] for r in rows} | set(held)))
    else:
        held = {}
        try:
            api = login()
            held = positions(api)
            px = snap_prices(api, sorted({r["code"] for r in rows} | set(held)))
            print("（dry-run：已登入模擬帳戶讀持股與報價，但不送單）")
        except Exception as e:
            print(f"（dry-run：模擬登入失敗，改用目標檔收盤價、持股當作 0：{e}）")
            px = file_prices(rows)
    orders, notes = plan(rows, held, px)
    tgt_codes = {r["code"] for r in rows}
    legacy = {c: q for c, q in held.items() if c not in tgt_codes}
    st0 = load_state()
    if "baseline" not in st0:
        base = {"start_date": date.today().isoformat(), "start_time": stamp(), "sleeve_ntd": TOTAL_MAX_NTD,
                "first_target_mon": mon, "legacy_positions": legacy,
                "note": "績效只算策略 100 萬子帳戶；舊持股（legacy）及其賣出所得不計入"}
        print("基準（送出時寫入 sim_state.json）：", json.dumps(base, ensure_ascii=False))
        if submit:
            st0["baseline"] = base
            save_state(st0)
    if legacy:
        print("舊持股（非策略，將清倉）：", legacy)
    print(f"目標 {mon}：{len(rows)} 檔；目前模擬持股 {len(held)} 檔；委託 {len(orders)} 筆")
    for o in orders:
        print(f"  {o['side']:4} {o['code']:>6} {o['lot']:11} qty={o['qty']:>4} 股數={o['shares']:>5} 限價={o['price']:>8} 金額={o['amount']:>8,}")
    for n in notes:
        print("  註：", n)
    if not submit:
        write_status(state="dry_run", mon=mon, orders=len(orders), notes=notes,
                     message=f"dry-run {len(orders)} 筆（未送出）")
        return 0
    logs, ok, bad = [], 0, 0
    for o in orders:
        check_stop()
        r = dict(o, time=stamp(), mon=mon, kind=kind)
        try:
            tr = safe_place(api, api.Contracts.Stocks[o["code"]], make_order(api, o))
            r["order_id"] = getattr(tr.order, "id", "")
            r["status"] = str(getattr(tr.status, "status", ""))
            r["msg"] = str(getattr(tr.status, "msg", ""))
            ok += 1
        except Exception as e:
            r["status"], r["msg"] = "ERROR", str(e)[:300]
            bad += 1
        logs.append(r)
    append_log(mon, logs)
    st = load_state()
    st.setdefault(mon, {})[kind] = stamp()
    st[mon]["last_trade_day"] = date.today().isoformat()
    save_state(st)
    write_status(state="submitted", mon=mon, orders=len(orders), ok=ok, errors=bad, notes=notes,
                 message=f"{kind} 送出模擬委託 {ok} 筆，失敗 {bad} 筆")
    print(f"已送模擬委託 {ok} 筆，失敗 {bad} 筆")
    return 0 if bad == 0 else 2


def reconcile() -> int:
    check_stop()
    t = latest_target()
    if not t:
        return 1
    mon, rows = t
    api = login()
    api.update_status(api.stock_account)
    out = []
    for tr in api.list_trades():
        o, s, c = tr.order, tr.status, tr.contract
        deals = getattr(s, "deals", []) or []
        dq = sum(int(d.quantity) for d in deals)
        lot = str(getattr(o, "order_lot", ""))
        mult = 1 if "Odd" in lot else 1000
        avg = (sum(float(d.price) * int(d.quantity) for d in deals) / dq) if dq else ""
        out.append({"time": stamp(), "mon": mon, "kind": "reconcile", "code": c.code,
                    "side": str(o.action).split(".")[-1], "lot": lot.split(".")[-1], "qty": o.quantity,
                    "shares": int(o.quantity) * mult, "price": o.price, "order_id": o.id,
                    "status": str(s.status).split(".")[-1], "deal_shares": dq * mult, "deal_avg": avg,
                    "msg": getattr(s, "msg", "")})
    append_log(mon, out)
    held = positions(api)
    rep = PAPER / f"sim_reconcile_{mon}.csv"
    px = snap_prices(api, sorted({r["code"] for r in rows}))
    ts_ = target_shares(rows, px)
    tgt = {r["code"]: (ts_[r["code"]], r.get("name", "")) for r in rows}
    miss = 0
    with rep.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["code", "name", "target_shares", "sim_shares", "diff"])
        for code in sorted(set(tgt) | set(held)):
            ts, nm = tgt.get(code, (0, ""))
            d = held.get(code, 0) - ts
            miss += d != 0
            w.writerow([code, nm, ts, held.get(code, 0), d])
    filled = sum(1 for r in out if r["status"] == "Filled")
    write_status(state="reconciled", mon=mon, trades=len(out), filled=filled, mismatched=miss,
                 message=f"對帳：委託 {len(out)} 筆、全部成交 {filled} 筆、與目標不符 {miss} 檔")
    print(f"對帳完成：委託 {len(out)}、成交 {filled}、不符 {miss} 檔 → {rep.name}")
    return 0


def nth_trading_day_of_month(d: date) -> int:
    if not tw_calendar.is_trading_day(d):
        return 0
    return sum(tw_calendar.is_trading_day(date(d.year, d.month, i)) for i in range(1, d.day + 1))


def auto(phase: str, retry: bool) -> int:
    check_stop()
    n = nth_trading_day_of_month(date.today())
    t = latest_target()
    if not t:
        print("沒有目標檔，結束"); return 0
    mon = t[0]
    st = load_state().get(mon, {})
    if phase == "open":
        if n == 1 and "open" not in st:
            return run(True, "open")
        if n == 2 and retry and "open" in st and "retry" not in st:
            return run(True, "retry")
        print(f"今天是本月第 {n} 個交易日，不需送單"); return 0
    if st.get("last_trade_day") == date.today().isoformat():
        return reconcile()
    print("今天沒有送單，不對帳"); return 0


def selftest() -> int:
    """0050 買 1 股零股，限價取跌停價（不會成交），送出後立刻刪單。只在模擬環境。"""
    check_stop()
    api = login()
    c = api.Contracts.Stocks["0050"]
    # 註：在盤後送出時，模擬環境可能直接拒絕或掛隔日；照實回報
    px = float(c.limit_down)
    o = {"code": "0050", "side": "Buy", "lot": "IntradayOdd", "qty": 1, "shares": 1, "price": px}
    tr = safe_place(api, c, make_order(api, o))
    print("送出：", tr.order.id, tr.status.status, getattr(tr.status, "msg", ""))
    api.update_status(api.stock_account)
    try:
        api.cancel_order(tr)
        api.update_status(api.stock_account)
        print("刪單後：", tr.status.status, getattr(tr.status, "msg", ""))
    except Exception as e:
        print("刪單失敗：", e)
    print("模擬持股檔數：", len(positions(api)))
    write_status(selftest=f"{stamp()} 0050 1股 送出→{tr.status.status}")
    return 0


# ---------------- 唯讀快照（給面板用） ----------------
SNAP_FILE = PAPER / "sim_snapshot.json"


def _f(x):
    try:
        return float(x)
    except Exception:
        return None


def snapshot() -> int:
    """只讀：持股、餘額、今日委託、已實現損益 → paper_nn/sim_snapshot.json。不送單。"""
    import shioaji as sj
    api = login()
    out = {"updated": stamp(), "simulation": True, "ok": True, "errors": []}
    st = load_state()
    base = st.get("baseline") or {}
    legacy = set((base.get("legacy_positions") or {}).keys()) if base else set()
    pos = []
    try:
        for p in api.list_positions(api.stock_account, unit=sj.constant.Unit.Share):
            q = int(p.quantity)
            if not q:
                continue
            avg, last = _f(p.price), _f(p.last_price)
            pnl = _f(getattr(p, "pnl", None))
            pos.append({"code": p.code, "shares": q, "avg": avg, "last": last, "pnl": pnl,
                        "ret": (last / avg - 1) if avg and last else None,
                        "mv": (last or 0) * q})
    except Exception as e:
        out["errors"].append(f"持股：{e}")
    out["positions"] = pos
    try:
        b = api.account_balance()
        out["balance"] = {"acc_balance": _f(getattr(b, "acc_balance", None)),
                          "date": str(getattr(b, "date", "")), "errmsg": str(getattr(b, "errmsg", ""))}
    except Exception as e:
        out["balance"] = None
        out["errors"].append(f"餘額：{e}")
    trades = []
    try:
        api.update_status(api.stock_account)
        for tr in api.list_trades():
            o, s = tr.order, tr.status
            lot = str(getattr(o, "order_lot", "")).split(".")[-1]
            mult = 1 if "Odd" in lot else 1000
            deals = getattr(s, "deals", []) or []
            dq = sum(int(d.quantity) for d in deals)
            trades.append({"code": tr.contract.code, "side": str(o.action).split(".")[-1], "lot": lot,
                           "shares": int(o.quantity) * mult, "price": _f(o.price), "status": str(s.status).split(".")[-1],
                           "deal_shares": dq * mult, "time": str(getattr(s, "order_datetime", "") or "")[:19],
                           "msg": str(getattr(s, "msg", ""))})
    except Exception as e:
        out["errors"].append(f"委託：{e}")
    out["trades"] = trades
    realized = 0.0
    if base.get("start_date"):
        try:
            for r in api.list_profit_loss(api.stock_account, begin_date=base["start_date"],
                                          end_date=date.today().isoformat()):
                if r.code not in legacy:
                    realized += float(r.pnl or 0)
        except Exception as e:
            out["errors"].append(f"已實現損益：{e}")
    if base:
        strat = [p for p in pos if p["code"] not in legacy]
        unreal = sum(p["pnl"] or 0 for p in strat)
        out["sleeve"] = {"start_date": base.get("start_date"), "initial": base.get("sleeve_ntd", TOTAL_MAX_NTD),
                         "unrealized": unreal, "realized": realized,
                         "equity": base.get("sleeve_ntd", TOTAL_MAX_NTD) + unreal + realized,
                         "mv": sum(p["mv"] for p in strat)}
    out["baseline"] = base or None
    out["legacy_codes"] = sorted(legacy) if base else sorted({p["code"] for p in pos} - {r["code"] for r in (latest_target() or ("", []))[1]})
    try:
        api.logout()
    except Exception:
        pass
    PAPER.mkdir(exist_ok=True)
    SNAP_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"快照完成：持股 {len(pos)} 檔、委託 {len(trades)} 筆、錯誤 {len(out['errors'])}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="NN 策略模擬送單（只准 simulation）")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--submit", action="store_true", help="送到永豐『模擬』帳戶")
    g.add_argument("--reconcile", action="store_true")
    g.add_argument("--auto", choices=["open", "close"])
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--snapshot", action="store_true", help="唯讀快照給面板")
    ap.add_argument("--retry", action="store_true", help="--auto open 時第二個交易日補單一次")
    a = ap.parse_args()
    try:
        if a.submit:
            return run(True)
        if a.reconcile:
            return reconcile()
        if a.auto:
            return auto(a.auto, a.retry)
        if a.selftest:
            return selftest()
        if a.snapshot:
            return snapshot()
        return run(False)
    except SystemExit:
        raise
    except Exception as e:
        write_status(state="error", message=f"{type(e).__name__}: {str(e)[:200]}")
        traceback.print_exc()
        return 3


if __name__ == "__main__":
    sys.exit(main())
