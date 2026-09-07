#!/workspace/trade/.venv/bin/python
"""Paper-trading daily runner: follow the tape with next-bar fills.

NOT a real broker. Single NT$1,000,000 portfolio, auto-select from a liquid
Taiwan universe, breakout_v2 + SNR_20 + TWII SMA60 + trailing stop.

Usage:
    /workspace/trade/.venv/bin/python paper_daily.py --live
    /workspace/trade/.venv/bin/python paper_daily.py --replay-from 2026-01-01 --replay-to 2026-08-13

Replay writes paper/replay/ and does not touch live paper/account.json.
Live writes paper/account.json for the latest session (and any missed days).
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
LIVE_STAMP = ROOT / "paper" / "last_live_run.txt"
TZ = ZoneInfo("Asia/Taipei")

import pandas as pd

from broker import at_limit_down, at_limit_up, buy_cost, buy_fill, sell_fill, try_buy_fill
from config import (
    COMMISSION_MIN,
    COMMISSION_RATE,
    INDEX_TICKER,
    INITIAL_CAPITAL,
    MAX_POSITIONS,
    PAPER_LOT_SIZE,
    PAPER_MAX_WEIGHT,
    SELL_TAX_RATE,
)
from paper_account import (
    PaperAccount,
    PaperPending,
    PaperPosition,
    PaperStore,
    default_live_dir,
    default_replay_dir,
)
from picker import format_rank_table, rank_candidates
from signals import (
    STRATEGY_NAME,
    TIME_STOP_DAYS,
    add_signal_columns,
    is_entry,
    is_time_stop_bar,
    is_trail_bar,
    tp_sl_hit,
)
from universe import (
    BANK_TICKERS,
    candidate_tickers,
    catalog_without_banks,
    display_name,
    load_prices,
    save_universe_csv,
    screen_universe,
    session_dates,
)
from news_risk import append_journal, evaluate_risk, name_heat, save_risk
from size_risk import (
    allocate_pool,
    append_size_journal,
    compute_pool,
    format_size_note,
    macro_pool_fraction,
    resolve_fill_budget,
)

log = logging.getLogger("trade.paper")

MAX_POSITIONS_DEFAULT = int(MAX_POSITIONS)


def _prev_close(df: pd.DataFrame | None, d: pd.Timestamp, ticker: str | None = None) -> float | None:
    d = pd.Timestamp(d).normalize()

    def _from(frame: pd.DataFrame | None) -> float | None:
        if frame is None or frame.empty or "Close" not in frame.columns:
            return None
        s = frame["Close"].copy()
        s.index = pd.to_datetime(s.index).normalize()
        s = s[~s.index.duplicated(keep="last")].sort_index().dropna()
        s = s[s.index < d]
        if s.empty:
            return None
        return float(s.iloc[-1])

    px = _from(df)
    if px is not None:
        return px
    if not ticker:
        return None
    try:
        from data import load_cache

        return _from(load_cache(ticker, end_date=None))
    except Exception:
        return None


def _bar(df: pd.DataFrame, d: pd.Timestamp) -> pd.Series | None:
    d = pd.Timestamp(d).normalize()
    if d not in df.index:
        return None
    row = df.loc[d]
    if isinstance(row, pd.DataFrame):
        row = row.iloc[-1]
    return row


def _last_close(df: pd.DataFrame, d: pd.Timestamp) -> float | None:
    hist = df[df.index <= pd.Timestamp(d).normalize()]
    if hist.empty:
        return None
    return float(hist.iloc[-1]["Close"])


def mark_to_market(acct: PaperAccount, prepared: dict[str, pd.DataFrame], d: pd.Timestamp) -> tuple[float, float]:
    mv = 0.0
    for pos in acct.positions:
        df = prepared.get(pos.ticker)
        px = None
        if df is not None:
            px = _last_close(df, d)
        if px is None:
            px = float(pos.avg_price)
        mv += pos.shares * px
    equity = float(acct.cash) + mv
    acct.equity = equity
    return mv, equity


def _ledger_equity(acct: PaperAccount, prepared: dict[str, pd.DataFrame], d: pd.Timestamp) -> float:
    mv, eq = mark_to_market(acct, prepared, d)
    return eq


def fill_pending_sells(
    acct: PaperAccount,
    prepared: dict[str, pd.DataFrame],
    d: pd.Timestamp,
    store: PaperStore,
    notes: list[str],
) -> None:
    still: list[PaperPending] = []
    dstr = pd.Timestamp(d).strftime("%Y-%m-%d")
    for pend in list(acct.pending):
        if pend.side != "sell":
            still.append(pend)
            continue
        df = prepared.get(pend.ticker)
        row = _bar(df, d) if df is not None else None
        if row is None:
            still.append(pend)
            notes.append(f"PENDING_SELL 仍等待開盤: {pend.ticker} ({pend.reason})")
            continue
        pos = acct.get_position(pend.ticker)
        if pos is None or pos.shares <= 0:
            notes.append(f"PENDING_SELL 無持倉已丟棄: {pend.ticker}")
            continue
        o = float(row["Open"])
        prev = _prev_close(df, d, pend.ticker)
        if at_limit_down(o, prev):
            still.append(pend)
            notes.append(
                f"PENDING_SELL 開盤跌停不成交（跟盤，改掛明天）: {pend.ticker} "
                f"open={o:.2f} prev={prev:.2f}"
            )
            continue
        fill = sell_fill(pos.shares, o, COMMISSION_RATE, COMMISSION_MIN, SELL_TAX_RATE)
        acct.cash = acct.cash + fill.cash_delta
        acct.drop_position(pend.ticker)
        eq = _ledger_equity(acct, prepared, d)
        store.append_ledger(
            {
                "date": dstr,
                "ticker": pend.ticker,
                "action": "sell",
                "reason": pend.reason,
                "price": round(fill.price, 4),
                "shares": fill.shares,
                "cash": round(acct.cash, 2),
                "equity": round(eq, 2),
                "snr": "",
            }
        )
        notes.append(
            f"SELL {pend.ticker} {pos.name} {fill.shares}股 @ {fill.price:.2f} "
            f"reason={pend.reason} cash={acct.cash:.0f}"
        )
    acct.pending = still


def fill_pending_buys(
    acct: PaperAccount,
    prepared: dict[str, pd.DataFrame],
    d: pd.Timestamp,
    store: PaperStore,
    max_positions: int,
    notes: list[str],
) -> None:
    dstr = pd.Timestamp(d).strftime("%Y-%m-%d")
    others: list[PaperPending] = []
    buys: list[PaperPending] = []
    for pend in list(acct.pending):
        if pend.side == "buy":
            buys.append(pend)
        else:
            others.append(pend)

    fillable: list[PaperPending] = []
    waiting: list[PaperPending] = []
    held = acct.held_tickers()
    for pend in buys:
        if pend.ticker in held:
            notes.append(f"PENDING_BUY 已持有，跳過: {pend.ticker}")
            continue
        df = prepared.get(pend.ticker)
        row = _bar(df, d) if df is not None else None
        if row is None:
            waiting.append(pend)
            notes.append(f"PENDING_BUY 仍等待開盤: {pend.ticker}")
            continue
        fillable.append(pend)

    slots = max(0, max_positions - len(acct.positions))
    waiting.extend(fillable[slots:])
    fillable = fillable[:slots]
    n = len(fillable)
    if n == 0:
        acct.pending = others + waiting
        return

    notes.append(
        f"資金分配: 昨日排隊預算池配置（單檔上限 {PAPER_MAX_WEIGHT:.0%} 權益、"
        f"先試 {PAPER_LOT_SIZE} 股再試 1 股，不 all-in；買不起則跳過並保留現金給同輪其他檔）"
    )
    for pend in fillable:
        if len(acct.positions) >= max_positions:
            waiting.append(pend)
            continue
        df = prepared[pend.ticker]
        row = _bar(df, d)
        o = float(row["Open"])
        prev = _prev_close(df, d, pend.ticker)
        if at_limit_up(o, prev):
            notes.append(
                f"PENDING_BUY 開盤漲停不成交（跟盤，不追價）: {pend.ticker} "
                f"open={o:.2f} prev={prev:.2f}"
            )
            continue
        slots_left = max(1, max_positions - len(acct.positions))
        _, equity = mark_to_market(acct, prepared, d)
        stored = getattr(pend, "target_budget", None)
        w = pend.target_weight
        budget = resolve_fill_budget(
            stored_budget=stored,
            target_weight=w,
            cash=float(acct.cash),
            equity=float(equity),
            slots_left=slots_left,
            max_weight=float(PAPER_MAX_WEIGHT),
        )
        if budget <= 0:
            notes.append(f"PENDING_BUY 預算 0，跳過: {pend.ticker} {pend.size_note}")
            continue
        fill, lot_used = try_buy_fill(
            budget, o, PAPER_LOT_SIZE, COMMISSION_RATE, COMMISSION_MIN, fallback_lot=1
        )
        if fill is None:
            # Do not infinite re-queue expensive names; leave cash for later names this pass.
            need1 = buy_cost(1, o, COMMISSION_RATE, COMMISSION_MIN)
            notes.append(
                f"PENDING_BUY 單股也買不起，放棄: {pend.ticker} {pend.name} "
                f"alloc={budget:.0f} need1={need1:.0f} open={o:.2f} cash={acct.cash:.0f}"
            )
            continue
        if lot_used == 1 and int(PAPER_LOT_SIZE) != 1:
            pend.size_note = (
                (pend.size_note + " ") if pend.size_note else ""
            ) + "lot=1零股"
            notes.append(
                f"PENDING_BUY {pend.ticker} 買不起{PAPER_LOT_SIZE}股，改以 1 股零股成交 "
                f"alloc={budget:.0f} open={o:.2f}"
            )
        acct.cash = acct.cash + fill.cash_delta
        pos = PaperPosition(
            ticker=pend.ticker,
            name=pend.name,
            shares=fill.shares,
            avg_price=fill.price,
            entry_date=dstr,
            entry_snr=pend.snr,
            time_stop_count=0,
            trail_armed=False,
        )
        acct.positions.append(pos)
        held.add(pend.ticker)
        eq = _ledger_equity(acct, prepared, d)
        snr_val = "" if pend.snr is None else round(float(pend.snr), 4)
        store.append_ledger(
            {
                "date": dstr,
                "ticker": pend.ticker,
                "action": "buy",
                "reason": pend.reason,
                "price": round(fill.price, 4),
                "shares": fill.shares,
                "cash": round(acct.cash, 2),
                "equity": round(eq, 2),
                "snr": snr_val,
            }
        )
        w_disp = "" if w is None else f" share={float(w):.0%}"
        notes.append(
            f"BUY {pend.ticker} {pend.name} {fill.shares}股 @ {fill.price:.2f} "
            f"snr={snr_val}{w_disp} budget={budget:.0f} cash={acct.cash:.0f}"
            + (f" {pend.size_note}" if pend.size_note else "")
        )

    acct.pending = others + waiting


def manage_exits(
    acct: PaperAccount,
    prepared: dict[str, pd.DataFrame],
    d: pd.Timestamp,
    notes: list[str],
) -> None:
    """Queue PENDING_SELL on TP/SL or 3-day support break. Fill is next open."""
    dstr = pd.Timestamp(d).strftime("%Y-%m-%d")
    d_ts = pd.Timestamp(d).normalize()
    for pos in list(acct.positions):
        if pos.shares <= 0:
            continue
        df = prepared.get(pos.ticker)
        row = _bar(df, d) if df is not None else None
        if row is None:
            continue
        entry = pd.Timestamp(pos.entry_date).normalize()
        if d_ts < entry:
            continue
        if acct.has_pending(pos.ticker, "sell"):
            # still update time-stop count
            pass
        else:
            o = float(row["Open"])
            h = float(row["High"])
            l = float(row["Low"])
            reason, _level = tp_sl_hit(float(pos.avg_price), h, l, o)
            if reason is None:
                armed, trail_hit = is_trail_bar(row, float(pos.avg_price), bool(getattr(pos, "trail_armed", False)))
                pos.trail_armed = armed
                if trail_hit:
                    reason = "trail"
            if reason is not None:
                acct.pending.append(
                    PaperPending(
                        side="sell",
                        ticker=pos.ticker,
                        name=pos.name,
                        reason=reason,
                        snr=pos.entry_snr,
                        signal_date=dstr,
                    )
                )
                notes.append(
                    f"QUEUE SELL {pos.ticker} {reason} (entry={pos.avg_price:.2f} "
                    f"H={h:.2f} L={l:.2f}) → 下一根開盤成交"
                )

        if is_time_stop_bar(row):
            pos.time_stop_count = int(pos.time_stop_count) + 1
        else:
            pos.time_stop_count = 0
        if pos.time_stop_count >= TIME_STOP_DAYS and not acct.has_pending(pos.ticker, "sell"):
            acct.pending.append(
                PaperPending(
                    side="sell",
                    ticker=pos.ticker,
                    name=pos.name,
                    reason="time_stop",
                    snr=pos.entry_snr,
                    signal_date=dstr,
                )
            )
            notes.append(
                f"QUEUE SELL {pos.ticker} time_stop "
                f"({pos.time_stop_count} 根收盤跌破前20日低) → 下一根開盤成交"
            )


def queue_risk_exits(
    acct: PaperAccount,
    risk: dict,
    d: pd.Timestamp,
    notes: list[str],
) -> None:
    """If market-stress switch is on, flatten next open (news-stop proxy in replay).

    Replay has no historical headlines; price_pause stands in for 消息面停損.
    Does not change live unless process_day(..., flat_on_risk=True).
    """
    if not risk.get("price_pause"):
        return
    dstr = pd.Timestamp(d).strftime("%Y-%m-%d")
    # drop all pending buys — do not open into a stress day
    kept = []
    n_drop = 0
    for p in list(acct.pending):
        if p.side == "buy":
            n_drop += 1
        else:
            kept.append(p)
    acct.pending = kept
    if n_drop:
        notes.append(f"風險停損：取消 {n_drop} 筆 pending buy")
    n_new = 0
    for pos in list(acct.positions):
        if pos.shares <= 0:
            continue
        if acct.has_pending(pos.ticker, "sell"):
            continue
        acct.pending.append(
            PaperPending(
                side="sell",
                ticker=pos.ticker,
                name=pos.name,
                reason="risk_stop",
                snr=pos.entry_snr,
                signal_date=dstr,
            )
        )
        n_new += 1
        notes.append(
            f"QUEUE SELL {pos.ticker} risk_stop（大盤壓力 "
            f"d1={risk.get('twii_d1')} d3={risk.get('twii_d3')}）→ 下一根開盤成交"
        )
    if n_new == 0 and n_drop == 0:
        notes.append("風險停損：大盤壓力但無持倉／已在排隊出")


def queue_entries(
    acct: PaperAccount,
    prepared: dict[str, pd.DataFrame],
    names: dict[str, str],
    passed: list[str],
    d: pd.Timestamp,
    max_positions: int,
    notes: list[str],
    allow_new: bool = True,
    fetch_news: bool = False,
    risk: dict | None = None,
    store: PaperStore | None = None,
    max_new_cap: int | None = None,
) -> list[dict]:
    dstr = pd.Timestamp(d).strftime("%Y-%m-%d")
    signal_rows: list[dict] = []
    for ticker in passed:
        df = prepared.get(ticker)
        row = _bar(df, d) if df is not None else None
        if row is None:
            continue
        if not is_entry(row):
            continue
        snr = float(row["snr_20"]) if pd.notna(row.get("snr_20")) else 0.0
        rs = float(row["rs_20"]) if pd.notna(row.get("rs_20")) else 0.0
        signal_rows.append(
            {
                "ticker": ticker,
                "name": names.get(ticker, ticker),
                "snr": snr,
                "rs": rs,
                "close": float(row["Close"]),
            }
        )

    held = acct.held_tickers()
    pending_all = acct.pending_tickers()
    n_slots = max(0, max_positions - len(acct.positions) - len(acct.pending_tickers("buy")))
    # do not add names already held or already pending (buy or sell)
    risk = risk or {}
    if not allow_new:
        notes.append("風險硬關：今日暫停開新倉（戰爭級／盤崩／新聞偏熱且紅盤／無新聞資料；舊倉照停利停損）")
        n_slots = 0
    elif max_new_cap is not None:
        before = n_slots
        n_slots = min(n_slots, max(0, int(max_new_cap)))
        if before > n_slots or int(max_new_cap) <= 1:
            notes.append(
                f"情緒軟關：新聞偏熱但未達硬關，今日新排隊上限 {int(max_new_cap)} 檔"
                f"（原空槽 {before}）"
            )
    picked = rank_candidates(signal_rows, held=held, pending=pending_all, max_new=n_slots)
    picked_set = {r["ticker"] for r in picked}
    notes.append(f"訊號 {len(signal_rows)} 檔，空槽 {n_slots}，新排隊 {len(picked)}")
    notes.append("排名:\n" + format_rank_table(signal_rows, picked_set))
    from datetime import datetime, timezone, timedelta

    taipei = timezone(timedelta(hours=8))
    now_iso = datetime.now(taipei).strftime("%Y-%m-%d %H:%M:%S%z")
    journal_root = store.root if store is not None else None

    macro_trend = str(risk.get("trend") or "cool")
    lock_new = bool(risk.get("lock_new"))
    # size_weight in news_risk is the macro pool fraction (cool 20% … severe 2%)
    if risk.get("size_weight") is not None:
        macro_frac = float(risk.get("size_weight"))
    else:
        macro_frac = macro_pool_fraction(macro_trend, lock_new)

    deployable_cash = float(acct.cash)
    pool = compute_pool(deployable_cash, macro_trend, lock_new)
    # If risk already forced frac=0 via lock, pool is 0; keep explicit.
    if lock_new:
        pool = 0.0
    elif risk.get("size_weight") is not None:
        pool = max(0.0, deployable_cash * macro_frac)

    # Fetch name heat for picked names, then allocate the pool across them.
    picked_meta: list[dict] = []
    heat_by: dict[str, dict] = {}
    for r in picked:
        nh: dict = {}
        if fetch_news:
            try:
                nh = name_heat(r["ticker"], r["name"], d)
            except Exception as exc:  # noqa: BLE001
                notes.append(f"個股新聞失敗 {r['ticker']}: {exc}")
                nh = {}
        heat_by[r["ticker"]] = nh
        name_trend = str(nh.get("trend") or "cool")
        name_lock = bool(nh.get("lock"))
        picked_meta.append(
            {
                "ticker": r["ticker"],
                "name": r["name"],
                "snr": r["snr"],
                "close": r["close"],
                "name_trend": name_trend,
                "name_lock": name_lock,
                "name_heat": nh.get("news_score", ""),
            }
        )

    _, equity_now = mark_to_market(acct, prepared, d) if picked_meta else (0.0, float(acct.equity))

    # Drop names where even 1 share (+fees) exceeds max possible single-name budget.
    # Remaining candidates keep / redistribute the pool.
    max_one_cap = min(float(deployable_cash), float(pool)) if pool > 0 else 0.0
    if equity_now and PAPER_MAX_WEIGHT:
        max_one_cap = min(max_one_cap, float(equity_now) * float(PAPER_MAX_WEIGHT))
    affordable_meta: list[dict] = []
    for m in picked_meta:
        px = float(m["close"])
        need1 = buy_cost(1, px, COMMISSION_RATE, COMMISSION_MIN)
        if max_one_cap <= 0 or need1 > max_one_cap + 1e-8:
            notes.append(
                f"QUEUE SKIP {m['ticker']} {m['name']} 單股也買不起 "
                f"close={px:.2f} need1={need1:.0f} cap={max_one_cap:.0f}"
            )
            continue
        affordable_meta.append(m)

    allocated = allocate_pool(
        pool,
        affordable_meta,
        equity=float(equity_now),
        max_weight=float(PAPER_MAX_WEIGHT),
    )

    # After split, some allocs may still be < 1 share; drop and re-allocate once.
    keep_meta: list[dict] = []
    for a in allocated:
        px = float(a["close"])
        need1 = buy_cost(1, px, COMMISSION_RATE, COMMISSION_MIN)
        budget_a = float(a.get("budget") or 0.0)
        share_w = float(a.get("share_w") or 0.0)
        if share_w <= 0 or budget_a <= 0:
            # locked / zero — leave out of re-alloc (already 0)
            continue
        if budget_a + 1e-8 < need1:
            notes.append(
                f"QUEUE SKIP {a['ticker']} {a['name']} 單股也買不起 "
                f"alloc={budget_a:.0f} need1={need1:.0f} close={px:.2f}"
            )
            continue
        keep_meta.append(
            {
                "ticker": a["ticker"],
                "name": a["name"],
                "snr": a["snr"],
                "close": a["close"],
                "name_trend": a.get("name_trend"),
                "name_lock": a.get("name_lock"),
                "name_heat": a.get("name_heat"),
            }
        )
    if keep_meta and len(keep_meta) < len(affordable_meta):
        allocated = allocate_pool(
            pool,
            keep_meta,
            equity=float(equity_now),
            max_weight=float(PAPER_MAX_WEIGHT),
        )
    elif not keep_meta:
        allocated = []
    alloc_by = {a["ticker"]: a for a in allocated}

    if picked:
        notes.append(
            f"預算池: cash={deployable_cash:.0f} macro={macro_trend}/{macro_frac:.0%} "
            f"pool={pool:.0f} 候選={len(picked)} 可負擔={len(alloc_by)}（依個股熱度分配；"
            f"先試{PAPER_LOT_SIZE}股再試1股）"
        )

    for r in signal_rows:
        nh = heat_by.get(r["ticker"], {})
        name_trend = str(nh.get("trend") or ("cool" if r["ticker"] in alloc_by else ""))
        name_lock = bool(nh.get("lock")) if nh else False
        a = alloc_by.get(r["ticker"])
        if a is not None:
            share = float(a.get("share") or 0.0)
            alloc = float(a.get("budget") or 0.0)
            tw = float(a.get("target_weight") or 0.0)
            size_note = format_size_note(
                pool=pool,
                macro_trend=macro_trend,
                macro_frac=macro_frac,
                name_trend=str(a.get("name_trend") or name_trend or "cool"),
                name_heat=a.get("name_heat", nh.get("news_score", "")),
                share=share,
                alloc=alloc,
            )
        else:
            share = 0.0
            alloc = 0.0
            tw = 0.0
            size_note = (
                f"pool={pool:.0f} macro={macro_trend}/{macro_frac:.0%} "
                f"name={name_trend or '-'}/{nh.get('news_score', '')} （未入隊）"
            )

        if r["ticker"] in alloc_by and alloc > 0:
            # Final guard: skip if even 1 share > this alloc (should be rare after re-alloc).
            need1 = buy_cost(1, float(r["close"]), COMMISSION_RATE, COMMISSION_MIN)
            if alloc + 1e-8 < need1:
                notes.append(
                    f"QUEUE SKIP {r['ticker']} {r['name']} 單股也買不起 "
                    f"alloc={alloc:.0f} need1={need1:.0f} {size_note}"
                )
                continue
            acct.pending.append(
                PaperPending(
                    side="buy",
                    ticker=r["ticker"],
                    name=r["name"],
                    reason=STRATEGY_NAME,
                    snr=r["snr"],
                    signal_date=dstr,
                    target_weight=tw,
                    target_budget=alloc,
                    name_heat=(None if nh.get("news_score") in (None, "") else float(nh["news_score"])),
                    name_trend=str(a.get("name_trend") or name_trend or "cool"),
                    name_lock=name_lock,
                    size_note=size_note,
                )
            )
            notes.append(
                f"QUEUE BUY {r['ticker']} {r['name']} snr={r['snr']:.4f} "
                f"alloc={alloc:.0f} {size_note} close={r['close']:.2f} → 下一根開盤成交"
            )
        elif r["ticker"] in alloc_by and alloc <= 0:
            notes.append(f"QUEUE SKIP {r['ticker']} {r['name']} 個股硬關或分配為0 {size_note}")
        try:
            append_size_journal(
                {
                    "logged_at": now_iso,
                    "session": dstr,
                    "ticker": r["ticker"],
                    "name": r["name"],
                    "macro_trend": macro_trend,
                    "macro_heat": risk.get("news_score", ""),
                    "macro_weight": macro_frac,
                    "war_lock": int(bool(risk.get("war_lock"))),
                    "old_switch_would_block": int(bool(risk.get("old_switch_would_block"))),
                    "lock_new": int(lock_new),
                    "name_heat": nh.get("news_score", "") if nh else "",
                    "name_trend": (str(a.get("name_trend") or name_trend) if a is not None else (name_trend or "")),
                    "name_lock": int(name_lock),
                    "target_weight": tw,
                    "shares": "",
                    "budget": (alloc if a is not None else ""),
                    "note": size_note,
                },
                root=journal_root,
            )
        except Exception:
            pass
    return signal_rows



def process_day(
    d: pd.Timestamp,
    acct: PaperAccount,
    store: PaperStore,
    prepared: dict[str, pd.DataFrame],
    names: dict[str, str],
    max_positions: int,
    failed: list[str],
    fetch_news: bool = False,
    flat_on_risk: bool = False,
) -> None:
    d = pd.Timestamp(d).normalize()
    dstr = d.strftime("%Y-%m-%d")
    if acct.last_session and pd.Timestamp(acct.last_session).normalize() >= d:
        log.info("skip %s (already processed, last_session=%s)", dstr, acct.last_session)
        return

    notes: list[str] = []
    notes.append(f"## {dstr}")
    notes.append(
        f"開始: cash={acct.cash:.0f} 持倉={len(acct.positions)} "
        f"pending={len(acct.pending)} equity={acct.equity:.0f}"
    )

    # 1. Open: fill yesterday's pending (sells first, then equal-weight buys)
    fill_pending_sells(acct, prepared, d, store, notes)
    fill_pending_buys(acct, prepared, d, store, max_positions, notes)

    # 2. Exits on today's bar → next open
    manage_exits(acct, prepared, d, notes)

    # 3. Liquidity screen + entries on today's close
    passed, table = screen_universe(prepared, names, d)
    save_universe_csv(table, store.universe_path)
    notes.append(f"流動性篩選通過 {len(passed)}/{len(names)} 檔（失敗下載 {len(failed)}）")
    twii = prepared.get(INDEX_TICKER)
    risk = evaluate_risk(d, twii=twii, fetch_news=fetch_news)
    save_risk(risk, store.root / "news_risk.json")
    notes.append(
        f"風險判定 lock_new={risk.get('lock_new')} soft_cap={risk.get('soft_cap')} "
        f"max_new={risk.get('max_new_entries')} size={risk.get('size_weight')} "
        f"news={risk['news_score']} red_day={risk.get('red_day')} "
        f"twii_d1={risk['twii_d1']} twii_d3={risk['twii_d3']}｜{risk['reason']}"
    )
    if flat_on_risk:
        queue_risk_exits(acct, risk, d, notes)
    _max_cap = risk.get("max_new_entries")
    queue_entries(
        acct, prepared, names, passed, d, max_positions, notes,
        allow_new=not bool(risk.get("lock_new", not risk.get("allow_new_entries", True))),
        fetch_news=fetch_news,
        risk=risk,
        store=store,
        max_new_cap=(None if _max_cap is None else int(_max_cap)),
    )

    # 4. Mark to market at D close
    mv, eq = mark_to_market(acct, prepared, d)
    store.append_equity(dstr, acct.cash, mv, eq)
    acct.last_session = dstr
    store.save_account(acct)

    held_s = ", ".join(
        f"{p.ticker} {p.shares}@{p.avg_price:.1f}" for p in acct.positions
    ) or "(空手)"
    pend_s = ", ".join(f"{p.side}:{p.ticker}/{p.reason}" for p in acct.pending) or "(無)"
    notes.append(
        f"收盤: cash={acct.cash:.0f} MV={mv:.0f} equity={eq:.0f} 持倉={held_s} pending={pend_s}"
    )
    store.append_log("\n".join(notes))
    if fetch_news:
        append_journal(
            {**risk, "slot": "close"},
            extra={
                "cash": round(float(acct.cash), 2),
                "equity": round(float(eq), 2),
                "n_positions": len(acct.positions),
                "holdings": "／".join(p.name or p.ticker for p in acct.positions),
            },
        )
    log.info("%s equity=%.0f cash=%.0f pos=%d pending=%d", dstr, eq, acct.cash, len(acct.positions), len(acct.pending))


def prepare_all(
    prices: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    twii = prices.get(INDEX_TICKER)
    out: dict[str, pd.DataFrame] = {}
    for ticker, df in prices.items():
        if ticker == INDEX_TICKER:
            out[ticker] = add_signal_columns(df, twii=None)
        else:
            out[ticker] = add_signal_columns(df, twii=twii)
    return out


def summarize(store: PaperStore, acct: PaperAccount) -> dict:
    summary = {
        "start_cash": acct.initial_cash,
        "end_equity": acct.equity,
        "end_cash": acct.cash,
        "n_positions": len(acct.positions),
        "n_pending": len(acct.pending),
        "n_round_trips": 0,
        "n_wins": 0,
        "win_rate": None,
        "n_buys": 0,
        "top_names": [],
        "open_holdings": [
            {
                "ticker": p.ticker,
                "name": p.name,
                "shares": p.shares,
                "avg_price": p.avg_price,
                "entry_date": p.entry_date,
            }
            for p in acct.positions
        ],
    }
    if not store.ledger_path.exists():
        return summary
    led = pd.read_csv(store.ledger_path, encoding="utf-8-sig")
    if led.empty:
        return summary
    buys = led[led["action"].astype(str) == "buy"]
    sells = led[led["action"].astype(str) == "sell"]
    summary["n_buys"] = int(len(buys))
    counts = Counter(buys["ticker"].astype(str).tolist())
    summary["top_names"] = counts.most_common(10)

    # FIFO round-trips per ticker using shares
    open_lots: dict[str, list[tuple[float, int]]] = {}
    wins = 0
    trips = 0
    for _, row in led.iterrows():
        t = str(row["ticker"])
        shares = int(row["shares"])
        px = float(row["price"])
        if str(row["action"]) == "buy":
            open_lots.setdefault(t, []).append((px, shares))
        elif str(row["action"]) == "sell":
            remain = shares
            cost = 0.0
            matched = 0
            lots = open_lots.get(t, [])
            while remain > 0 and lots:
                ep, es = lots[0]
                take = min(es, remain)
                cost += ep * take
                matched += take
                remain -= take
                if take == es:
                    lots.pop(0)
                else:
                    lots[0] = (ep, es - take)
            if matched > 0:
                trips += 1
                proceeds = px * matched
                if proceeds > cost:
                    wins += 1
    summary["n_round_trips"] = trips
    summary["n_wins"] = wins
    summary["win_rate"] = (wins / trips) if trips else None
    return summary


def print_summary(summary: dict, failed: list[str], store: PaperStore) -> None:
    wr = summary["win_rate"]
    wr_s = "n/a" if wr is None else f"{wr*100:.1f}%"
    print("==== PAPER REPLAY / RUN SUMMARY ====")
    print(f"dir:          {store.root}")
    print(f"start cash:   {summary['start_cash']:.0f}")
    print(f"end equity:   {summary['end_equity']:.0f}")
    print(f"end cash:     {summary['end_cash']:.0f}")
    print(f"buys:         {summary['n_buys']}")
    print(f"round trips:  {summary['n_round_trips']}")
    print(f"wins:         {summary['n_wins']}")
    print(f"win rate:     {wr_s}")
    print("top names (buy count):")
    for t, n in summary["top_names"]:
        print(f"  {t}: {n}")
    print("open holdings:")
    for p in summary["open_holdings"]:
        print(f"  {p['ticker']} {p['name']} {p['shares']} @ {p['avg_price']:.2f} ({p['entry_date']})")
    if not summary["open_holdings"]:
        print("  (none)")
    print("pending:")
    print("  (see account.json)")
    if failed:
        print("failed tickers:")
        for t in failed:
            print(f"  {t}")
    else:
        print("failed tickers: (none)")
    print("====================================")


def load_prepared(
    force_download: bool = False,
    extra_tickers: list[str] | None = None,
    names: dict[str, str] | None = None,
) -> tuple[dict, dict, list[str]]:
    names = dict(names) if names is not None else candidate_tickers()
    tickers: list[str] = []
    for t in list(names.keys()) + list(extra_tickers or []) + [INDEX_TICKER]:
        if t and t not in tickers:
            tickers.append(t)
    # Do not clip to backtest END_DATE — paper must follow new sessions.
    prices, failed = load_prices(tickers, force_download=force_download, end_date=None)
    prepared = prepare_all(prices)
    return prepared, names, failed


def run_replay(
    start: str,
    end: str,
    max_positions: int,
    force_download: bool,
    reset: bool = True,
    replay_dir: Path | None = None,
    flat_on_risk: bool = False,
    exclude_banks: bool = False,
) -> None:
    root = Path(replay_dir) if replay_dir else default_replay_dir()
    store = PaperStore(root)
    if reset and store.root.exists():
        # fresh 1M for a proof replay
        for p in store.root.glob("*"):
            if p.is_file():
                p.unlink()
    store = PaperStore(root)
    acct = store.load_or_create(INITIAL_CAPITAL)
    extra = "；實驗：大盤壓力日隔日開盤出清舊倉" if flat_on_risk else ""
    names_ov = catalog_without_banks() if exclude_banks else None
    if exclude_banks:
        dropped = "、".join(f"{n}({t})" for t, n in BANK_TICKERS.items())
        extra += f"；不含銀行股：{dropped}"
        log.info("replay exclude banks: %s", sorted(BANK_TICKERS))
    store.write_log_header(
        f"紙上交易回放 {start} → {end}（非真實券商；訊號 t 收盤、t+1 開盤成交{extra}）"
    )
    extra = [p.ticker for p in acct.positions] + [p.ticker for p in acct.pending]
    prepared, names, failed = load_prepared(
        force_download=force_download, extra_tickers=extra, names=names_ov,
    )
    dates = session_dates(prepared, start=start, end=end)
    if len(dates) == 0:
        raise SystemExit("no session dates in replay window (check cache / TWII)")
    log.info(
        "replay %s → %s  days=%d  names=%d  flat_on_risk=%s  dir=%s  failed=%s",
        start, end, len(dates), len(names), flat_on_risk, store.root, failed,
    )
    (store.root / "failed_tickers.txt").write_text(
        "\n".join(failed) + ("\n" if failed else ""), encoding="utf-8"
    )
    for d in dates:
        process_day(
            d, acct, store, prepared, names, max_positions, failed,
            fetch_news=False, flat_on_risk=flat_on_risk,
        )
    summary = summarize(store, acct)
    print_summary(summary, failed, store)
    wr = summary["win_rate"]
    wr_s = "n/a" if wr is None else f"{wr * 100:.1f}%"
    lines = [
        "# Replay summary",
        f"- start cash: {summary['start_cash']:.0f}",
        f"- end equity: {summary['end_equity']:.0f}",
        f"- buys: {summary['n_buys']}",
        f"- round trips: {summary['n_round_trips']}",
        f"- win rate: {wr_s}",
        f"- failed: {', '.join(failed) if failed else '(none)'}",
        "",
    ]
    (store.root / "replay_summary.md").write_text("\n".join(lines), encoding="utf-8")


def _mark_live_stamp() -> None:
    LIVE_STAMP.parent.mkdir(parents=True, exist_ok=True)
    LIVE_STAMP.write_text(datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")


OPEN_STAMP = ROOT / "paper" / "last_open_fill.txt"


def _today_open_price(ticker: str) -> float | None:
    from quotes import get_feed

    feed = get_feed()
    bar = feed.session_bar(ticker)
    if bar and bar.get("Open"):
        px = float(bar["Open"])
        if px > 0:
            return px
    q = feed.last(ticker)
    if q is not None and q.open and float(q.open) > 0:
        return float(q.open)
    return None


def _open_bar_frame(day: pd.Timestamp, price: float) -> pd.DataFrame:
    d = pd.Timestamp(day).normalize()
    px = float(price)
    return pd.DataFrame(
        {"Open": [px], "High": [px], "Low": [px], "Close": [px]},
        index=[d],
    )


def run_open_fills(max_positions: int) -> int:
    """Fill yesterday's pending at today's open. Does not confirm new signals.

    Daily Yahoo cache has no t+1 bar at 08:30. Use 1-minute / live open instead.
    last_session stays yesterday so 16:00 can still process the close.
    """
    store = PaperStore(default_live_dir())
    acct = store.load_or_create(INITIAL_CAPITAL)
    now = datetime.now(TZ)
    today = pd.Timestamp(now.date()).normalize()
    if now.weekday() >= 5:
        log.info("open-fill skip: weekend")
        return 0
    if not acct.pending:
        log.info("open-fill skip: no pending")
        return 0
    last = pd.Timestamp(acct.last_session).normalize() if acct.last_session else None
    if last is not None and last >= today:
        log.info("open-fill skip: last_session already %s", acct.last_session)
        return 0
    if OPEN_STAMP.exists() and OPEN_STAMP.read_text(encoding="utf-8").strip()[:10] == today.strftime("%Y-%m-%d"):
        log.info("open-fill skip: already filled opens today")
        return 0

    try:
        from ui_settings import effective_strategy
        from config import STRATEGY_DEFAULTS

        overlay = effective_strategy(STRATEGY_DEFAULTS)
        max_positions = int(overlay.get("MAX_POSITIONS") or max_positions)
    except Exception:
        pass

    notes: list[str] = [f"## {today.strftime('%Y-%m-%d')} 開盤成交（pending）"]
    prepared: dict[str, pd.DataFrame] = {}
    missing = 0
    for pend in list(acct.pending):
        px = _today_open_price(pend.ticker)
        if px is None:
            notes.append(f"OPEN 還沒有開盤價: {pend.ticker} {pend.name}")
            missing += 1
            continue
        prepared[pend.ticker] = _open_bar_frame(today, px)
        notes.append(f"開盤價 {pend.ticker} {pend.name} {px:.2f}")
    fill_pending_sells(acct, prepared, today, store, notes)
    fill_pending_buys(acct, prepared, today, store, max_positions, notes)
    _, eq = mark_to_market(acct, prepared, today)
    acct.equity = eq
    store.save_account(acct)
    store.append_log("\n".join(notes) + "\n")
    if missing:
        log.info("open-fill waiting on %d quotes", missing)
        return 1
    OPEN_STAMP.write_text(now.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    log.info(
        "open-fill done pos=%d pending=%d cash=%.0f",
        len(acct.positions), len(acct.pending), acct.cash,
    )
    return 0


def run_live(max_positions: int, force_download: bool) -> None:
    store = PaperStore(default_live_dir())
    acct = store.load_or_create(INITIAL_CAPITAL)
    store.write_log_header("紙上交易（非真實券商）— live")
    now = datetime.now(TZ)
    today = pd.Timestamp(now.date()).normalize()

    extra = [p.ticker for p in acct.positions] + [p.ticker for p in acct.pending]
    prepared, names, failed = load_prepared(force_download=False, extra_tickers=extra)
    dates = session_dates(prepared)
    latest = dates[-1] if len(dates) else None
    last = pd.Timestamp(acct.last_session).normalize() if acct.last_session else None
    cache_ahead = bool(latest is not None and (last is None or last < latest))
    maybe_new_bar = (
        force_download
        and now.weekday() < 5
        and now.hour >= 15
        and (last is None or last < today)
        and not cache_ahead
    )
    if maybe_new_bar:
        log.info("live: cache has no new session, downloading (post-15:00 weekday)")
        prepared, names, failed = load_prepared(
            force_download=True, extra_tickers=extra,
        )
        dates = session_dates(prepared)
        latest = dates[-1] if len(dates) else None
        cache_ahead = bool(latest is not None and (last is None or last < latest))
    elif force_download and cache_ahead:
        log.info("live: cache already has unprocessed days, skip extra download")
    elif not cache_ahead:
        log.info(
            "live skip: no new session (last=%s latest=%s today=%s) — holiday/weekend or already done",
            acct.last_session, None if latest is None else latest.date(), today.date(),
        )
        print_summary(summarize(store, acct), failed, store)
        store.save_account(acct)
        _mark_live_stamp()
        return

    if acct.last_session is None:
        to_run = [latest]
        log.info("first live run → latest session %s", latest.date())
    else:
        last = pd.Timestamp(acct.last_session).normalize()
        to_run = [d for d in dates if d > last]
        if not to_run:
            log.info("live up to date (last_session=%s latest=%s)", acct.last_session, latest.date())
            print_summary(summarize(store, acct), failed, store)
            store.save_account(acct)
            _mark_live_stamp()
            return
    (store.root / "failed_tickers.txt").write_text(
        "\n".join(failed) + ("\n" if failed else ""), encoding="utf-8"
    )
    for d in to_run:
        process_day(d, acct, store, prepared, names, max_positions, failed, fetch_news=True)
    print_summary(summarize(store, acct), failed, store)
    _mark_live_stamp()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    ap = argparse.ArgumentParser(description="Taiwan paper trader (NOT a real broker)")
    ap.add_argument("--live", action="store_true", help="update paper/account.json for latest session")
    ap.add_argument("--opens", action="store_true", help="fill pending at today's live open only")
    ap.add_argument("--replay-from", dest="replay_from", default=None)
    ap.add_argument("--replay-to", dest="replay_to", default=None)
    ap.add_argument("--max-positions", type=int, default=MAX_POSITIONS_DEFAULT)
    ap.add_argument("--download", action="store_true", help="refresh live bars (Shioaji if logged in)")
    ap.add_argument("--keep-replay", action="store_true", help="do not wipe paper/replay before replay")
    ap.add_argument(
        "--flat-on-risk",
        action="store_true",
        help="replay/live: TWII stress also exits positions next open (news-stop proxy)",
    )
    ap.add_argument(
        "--replay-dir",
        default=None,
        help="replay output folder (default paper/replay)",
    )
    ap.add_argument(
        "--exclude-banks",
        action="store_true",
        help="replay only: drop 富邦金/國泰金/中信金/兆豐金. Does not change live.",
    )
    args = ap.parse_args()

    if args.replay_from or args.replay_to:
        if args.live:
            raise SystemExit("--exclude-banks / replay 不要跟 --live 一起跑")
        start = args.replay_from or "2026-01-01"
        end = args.replay_to or "2026-08-13"
        rdir = Path(args.replay_dir) if args.replay_dir else None
        run_replay(
            start,
            end,
            max_positions=args.max_positions,
            force_download=args.download,
            reset=not args.keep_replay,
            replay_dir=rdir,
            flat_on_risk=bool(args.flat_on_risk),
            exclude_banks=bool(args.exclude_banks),
        )
        return
    if args.opens:
        raise SystemExit(run_open_fills(max_positions=args.max_positions))
    if args.live:
        if args.exclude_banks:
            raise SystemExit("--exclude-banks 只用於回放，避免改到 live 持股")
        run_live(max_positions=args.max_positions, force_download=args.download)
        return
    ap.print_help()
    print("\nNeed --live or --replay-from/--replay-to", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
