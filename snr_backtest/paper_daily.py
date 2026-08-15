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
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from broker import buy_fill, sell_fill
from config import (
    COMMISSION_MIN,
    COMMISSION_RATE,
    INDEX_TICKER,
    INITIAL_CAPITAL,
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
    candidate_tickers,
    display_name,
    load_prices,
    save_universe_csv,
    screen_universe,
    session_dates,
)
from news_risk import evaluate_risk, save_risk

log = logging.getLogger("trade.paper")

MAX_POSITIONS_DEFAULT = 5


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
        f"資金分配: 單檔上限權益 {PAPER_MAX_WEIGHT:.0%}、"
        f"閒置現金/剩餘空槽，不 all-in 單一檔"
    )
    for pend in fillable:
        if len(acct.positions) >= max_positions:
            waiting.append(pend)
            continue
        df = prepared[pend.ticker]
        row = _bar(df, d)
        o = float(row["Open"])
        slots_left = max(1, max_positions - len(acct.positions))
        _, equity = mark_to_market(acct, prepared, d)
        cap_weight = float(equity) * float(PAPER_MAX_WEIGHT)
        cap_slot = float(acct.cash) / slots_left
        budget = min(float(acct.cash), cap_weight, cap_slot)
        fill = buy_fill(budget, o, PAPER_LOT_SIZE, COMMISSION_RATE, COMMISSION_MIN)
        if fill is None:
            notes.append(
                f"PENDING_BUY 買不起{PAPER_LOT_SIZE}股，現金留存: "
                f"{pend.ticker} alloc={budget:.0f} open={o:.2f}"
            )
            continue
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
        notes.append(
            f"BUY {pend.ticker} {pend.name} {fill.shares}股 @ {fill.price:.2f} "
            f"snr={snr_val} budget={budget:.0f} cash={acct.cash:.0f}"
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


def queue_entries(
    acct: PaperAccount,
    prepared: dict[str, pd.DataFrame],
    names: dict[str, str],
    passed: list[str],
    d: pd.Timestamp,
    max_positions: int,
    notes: list[str],
    allow_new: bool = True,
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
    if not allow_new:
        notes.append("風險開關：今日暫停開新倉（舊倉照停利停損）")
        n_slots = 0
    picked = rank_candidates(signal_rows, held=held, pending=pending_all, max_new=n_slots)
    picked_set = {r["ticker"] for r in picked}
    notes.append(f"訊號 {len(signal_rows)} 檔，空槽 {n_slots}，新排隊 {len(picked)}")
    notes.append("排名:\n" + format_rank_table(signal_rows, picked_set))

    for r in picked:
        acct.pending.append(
            PaperPending(
                side="buy",
                ticker=r["ticker"],
                name=r["name"],
                reason=STRATEGY_NAME,
                snr=r["snr"],
                signal_date=dstr,
            )
        )
        notes.append(
            f"QUEUE BUY {r['ticker']} {r['name']} snr={r['snr']:.4f} rs={r['rs']:.4f} "
            f"close={r['close']:.2f} → 下一根開盤成交"
        )
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
        f"風險判定 allow_new={risk['allow_new_entries']} news={risk['news_score']} "
        f"twii_d1={risk['twii_d1']} twii_d3={risk['twii_d3']}｜{risk['reason']}"
    )
    queue_entries(
        acct, prepared, names, passed, d, max_positions, notes,
        allow_new=bool(risk["allow_new_entries"]),
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


def load_prepared(force_download: bool = False) -> tuple[dict, dict, list[str]]:
    names = candidate_tickers()
    tickers = list(names.keys()) + [INDEX_TICKER]
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
) -> None:
    store = PaperStore(default_replay_dir())
    if reset and store.root.exists():
        # fresh 1M for a proof replay
        for p in store.root.glob("*"):
            if p.is_file():
                p.unlink()
    store = PaperStore(default_replay_dir())
    acct = store.load_or_create(INITIAL_CAPITAL)
    store.write_log_header(
        f"紙上交易回放 {start} → {end}（非真實券商；訊號 t 收盤、t+1 開盤成交）"
    )
    prepared, names, failed = load_prepared(force_download=force_download)
    dates = session_dates(prepared, start=start, end=end)
    if len(dates) == 0:
        raise SystemExit("no session dates in replay window (check cache / TWII)")
    log.info("replay %s → %s  days=%d  names=%d  failed=%s", start, end, len(dates), len(names), failed)
    (store.root / "failed_tickers.txt").write_text(
        "\n".join(failed) + ("\n" if failed else ""), encoding="utf-8"
    )
    for d in dates:
        process_day(d, acct, store, prepared, names, max_positions, failed, fetch_news=False)
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


def run_live(max_positions: int, force_download: bool) -> None:
    store = PaperStore(default_live_dir())
    acct = store.load_or_create(INITIAL_CAPITAL)
    store.write_log_header("紙上交易（非真實券商）— live")
    prepared, names, failed = load_prepared(force_download=force_download)
    dates = session_dates(prepared)
    if len(dates) == 0:
        raise SystemExit("no bars available")
    latest = dates[-1]
    if acct.last_session is None:
        # first live run: only the latest session (mostly queues pending buys)
        to_run = [latest]
        log.info("first live run → latest session %s", latest.date())
    else:
        last = pd.Timestamp(acct.last_session).normalize()
        to_run = [d for d in dates if d > last]
        if not to_run:
            log.info("live up to date (last_session=%s latest=%s)", acct.last_session, latest.date())
            print_summary(summarize(store, acct), failed, store)
            store.save_account(acct)
            return
    (store.root / "failed_tickers.txt").write_text(
        "\n".join(failed) + ("\n" if failed else ""), encoding="utf-8"
    )
    for d in to_run:
        process_day(d, acct, store, prepared, names, max_positions, failed, fetch_news=True)
    print_summary(summarize(store, acct), failed, store)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    ap = argparse.ArgumentParser(description="Taiwan paper trader (NOT a real broker)")
    ap.add_argument("--live", action="store_true", help="update paper/account.json for latest session")
    ap.add_argument("--replay-from", dest="replay_from", default=None)
    ap.add_argument("--replay-to", dest="replay_to", default=None)
    ap.add_argument("--max-positions", type=int, default=MAX_POSITIONS_DEFAULT)
    ap.add_argument("--download", action="store_true", help="force yfinance refresh")
    ap.add_argument("--keep-replay", action="store_true", help="do not wipe paper/replay before replay")
    args = ap.parse_args()

    if args.replay_from or args.replay_to:
        start = args.replay_from or "2026-01-01"
        end = args.replay_to or "2026-08-13"
        run_replay(
            start,
            end,
            max_positions=args.max_positions,
            force_download=args.download,
            reset=not args.keep_replay,
        )
        return
    if args.live:
        run_live(max_positions=args.max_positions, force_download=args.download)
        return
    ap.print_help()
    print("\nNeed --live or --replay-from/--replay-to", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
