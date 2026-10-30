"""Event-driven daily backtest: signal on t close, fill at t+1 open.

No same-bar entry. Intrabar TP/SL uses that bar's high/low; if both levels
are touched, SL is assumed first (conservative). A gap through a level fills
at the open, not at the theoretical stop.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from broker import buy_fill, sell_fill
from config import (
    COMMISSION_MIN,
    COMMISSION_RATE,
    END_DATE,
    INDEX_TICKER,
    INITIAL_CAPITAL,
    LOT_SIZE,
    SELL_TAX_RATE,
    START_DATE,
    TICKERS,
    TWII_SMA,
)
from indicators import bollinger as bb_calc
from indicators import kd as kd_calc
from indicators import macd as macd_calc
from indicators import rsi as rsi_calc
from strategies import StrategySpec, add_indicators


@dataclass
class Position:
    shares: int = 0
    entry_price: float = 0.0
    entry_date: pd.Timestamp | None = None
    signal_snr: float | None = None
    time_stop_count: int = 0
    trail_armed: bool = False


@dataclass
class Pending:
    side: str  # "buy" | "sell"
    reason: str
    snr: float | None = None


@dataclass
class BacktestResult:
    ticker: str
    name: str
    strategy: str
    trades: pd.DataFrame
    equity: pd.Series
    initial_capital: float
    failed: str | None = None


def _sell(
    pos: Position,
    cash: float,
    price: float,
    date,
    ticker: str,
    name: str,
    reason: str,
    close_for_mtm: float,
    trade_rows: list[dict],
) -> tuple[Position, float]:
    fill = sell_fill(pos.shares, price, COMMISSION_RATE, COMMISSION_MIN, SELL_TAX_RATE)
    cash = cash + fill.cash_delta
    equity = cash  # flat
    trade_rows.append(
        {
            "date": pd.Timestamp(date).strftime("%Y-%m-%d"),
            "ticker": ticker,
            "name": name,
            "action": "sell",
            "reason": reason,
            "price": round(fill.price, 4),
            "shares": fill.shares,
            "cash": round(cash, 2),
            "equity": round(equity, 2),
            "snr": "",
            "commission": round(fill.commission, 2),
            "tax": round(fill.tax, 2),
        }
    )
    return Position(), cash


def attach_twii(bars: pd.DataFrame, twii: pd.DataFrame | None) -> pd.DataFrame:
    """Join ^TWII close and SMA-60 onto ticker bars (ffill for calendar gaps)."""
    out = bars.copy()
    for col in ("twii_close", "twii_sma_60"):
        if col in out.columns:
            out = out.drop(columns=[col])
    if twii is None or twii.empty or "Close" not in twii.columns:
        out["twii_close"] = float("nan")
        out["twii_sma_60"] = float("nan")
        return out
    tw = twii[["Close"]].rename(columns={"Close": "twii_close"}).copy()
    tw["twii_sma_60"] = tw["twii_close"].rolling(TWII_SMA, min_periods=TWII_SMA).mean()
    out = out.join(tw, how="left")
    out["twii_close"] = out["twii_close"].ffill()
    out["twii_sma_60"] = out["twii_sma_60"].ffill()
    return out


def overlay_spec_indicators(bars: pd.DataFrame, spec: StrategySpec) -> pd.DataFrame:
    """Recompute columns that depend on user-tunable periods. Paper live still uses add_indicators defaults."""
    out = bars.copy()
    h, l, c = out["High"], out["Low"], out["Close"]
    n = max(2, int(spec.lookback or 20))
    if spec.kind == "breakout":
        out["prior_high_20"] = h.shift(1).rolling(n, min_periods=n).max()
        out["prior_low_20"] = l.shift(1).rolling(n, min_periods=n).min()
        tl = max(2, int(spec.trail_lookback or 15))
        out["prior_low_15"] = l.shift(1).rolling(tl, min_periods=tl).min()
    if spec.kind == "pullback":
        fast = max(2, int(spec.sma_fast or 20))
        trend = max(2, int(spec.sma_trend or 60))
        out["sma_20"] = c.rolling(fast, min_periods=fast).mean()
        out["sma_60"] = c.rolling(trend, min_periods=trend).mean()
    if spec.kind == "macd":
        m, s, _h = macd_calc(c, spec.macd_fast, spec.macd_slow, spec.macd_signal)
        out["macd"] = m
        out["macd_sig"] = s
        out["macd_prev"] = m.shift(1)
        out["macd_sig_prev"] = s.shift(1)
    if spec.kind == "rsi":
        r = rsi_calc(c, spec.rsi_n)
        out["rsi"] = r
        out["rsi_prev"] = r.shift(1)
    if spec.kind == "kd":
        k, d = kd_calc(h, l, c, spec.kd_n, spec.kd_k, spec.kd_d)
        out["k"] = k
        out["d"] = d
        out["k_prev"] = k.shift(1)
        out["d_prev"] = d.shift(1)
    if spec.kind == "sma":
        fast = max(2, int(spec.sma_fast or 20))
        slow = max(3, int(spec.sma_trend or 60))
        out["sma_fast"] = c.rolling(fast, min_periods=fast).mean()
        out["sma_slow"] = c.rolling(slow, min_periods=slow).mean()
        out["sma_fast_prev"] = out["sma_fast"].shift(1)
        out["sma_slow_prev"] = out["sma_slow"].shift(1)
    if spec.kind == "bb":
        mid, up, lo = bb_calc(c, spec.bb_n, spec.bb_k)
        out["bb_mid"] = mid
        out["bb_up"] = up
        out["bb_lo"] = lo
    return out


def run_one(
    df: pd.DataFrame,
    spec: StrategySpec,
    ticker: str,
    name: str,
    initial_capital: float = INITIAL_CAPITAL,
    start_date: str | None = None,
    end_date: str | None = None,
    twii: pd.DataFrame | None = None,
) -> BacktestResult:
    if df is None or df.empty:
        return BacktestResult(
            ticker, name, spec.name,
            pd.DataFrame(), pd.Series(dtype=float), initial_capital,
            failed="no data",
        )

    bars = add_indicators(df).sort_index()
    bars = overlay_spec_indicators(bars, spec)
    bars = attach_twii(bars, twii)
    start = pd.Timestamp(start_date or START_DATE)
    end = pd.Timestamp(end_date or END_DATE) if (end_date or END_DATE) else None
    if end is not None:
        bars = bars[bars.index <= end]
    trade_rows: list[dict] = []
    equity_pts: list[tuple[pd.Timestamp, float]] = []

    cash = initial_capital
    pos = Position()
    pending: Pending | None = None

    for i in range(len(bars)):
        row = bars.iloc[i]
        date = bars.index[i]
        o = float(row["Open"])
        h = float(row["High"])
        l = float(row["Low"])
        c = float(row["Close"])
        snr_t = float(row["snr_20"]) if pd.notna(row["snr_20"]) else 0.0
        in_window = date >= start

        # --- 1. Open: next-bar execution of yesterday's decision ---
        if in_window and pending is not None:
            if pending.side == "sell" and pos.shares > 0:
                pos, cash = _sell(
                    pos, cash, o, date, ticker, name, pending.reason, c, trade_rows
                )
                pending = None
            elif pending.side == "buy" and pos.shares == 0:
                fill = buy_fill(cash, o, LOT_SIZE, COMMISSION_RATE, COMMISSION_MIN)
                if fill is None:
                    pending = None
                else:
                    cash = cash + fill.cash_delta
                    pos = Position(
                        shares=fill.shares,
                        entry_price=fill.price,
                        entry_date=date,
                        signal_snr=pending.snr,
                        time_stop_count=0,
                        trail_armed=False,
                    )
                    trade_rows.append(
                        {
                            "date": pd.Timestamp(date).strftime("%Y-%m-%d"),
                            "ticker": ticker,
                            "name": name,
                            "action": "buy",
                            "reason": pending.reason,
                            "price": round(fill.price, 4),
                            "shares": fill.shares,
                            "cash": round(cash, 2),
                            "equity": round(cash + pos.shares * c, 2),
                            "snr": round(pending.snr, 4) if pending.snr is not None else "",
                            "commission": round(fill.commission, 2),
                            "tax": 0.0,
                        }
                    )
                    pending = None

        # --- 2. Intrabar TP / SL (including the entry bar, after open fill) ---
        if in_window and pos.shares > 0:
            sl_px = pos.entry_price * (1.0 - spec.sl)
            tp_px = pos.entry_price * (1.0 + spec.tp)
            hit_sl = l <= sl_px
            hit_tp = h >= tp_px
            exit_px = None
            reason = None
            if o <= sl_px:
                exit_px, reason = o, "sl"
            elif o >= tp_px:
                exit_px, reason = o, "tp"
            elif hit_sl and hit_tp:
                exit_px, reason = sl_px, "sl"  # conservative: SL first
            elif hit_sl:
                exit_px, reason = sl_px, "sl"
            elif hit_tp:
                exit_px, reason = tp_px, "tp"
            if exit_px is not None:
                pos, cash = _sell(
                    pos, cash, exit_px, date, ticker, name, reason, c, trade_rows
                )
                pending = None

        # --- 2b. Arm trailing stop once bar high vs fill >= trail_arm ---
        if in_window and pos.shares > 0 and spec.trail and not pos.trail_armed:
            if h >= pos.entry_price * (1.0 + spec.trail_arm):
                pos.trail_armed = True

        # --- 3. Close: mark to market ---
        mtm = cash + pos.shares * c
        if in_window:
            equity_pts.append((date, mtm))

        # Warmup bars still compute signals so the last pre-start close can
        # arm a next-open fill on the first in-window day.
        if pos.shares > 0:
            if spec.time_stop_trigger(row):
                pos.time_stop_count += 1
            else:
                pos.time_stop_count = 0
            pending_exit = None
            if spec.time_stop_days > 0 and pos.time_stop_count >= spec.time_stop_days:
                pending_exit = Pending(side="sell", reason="time_stop", snr=snr_t)
            if spec.trail and pos.trail_armed and spec.trail_trigger(row):
                pending_exit = Pending(side="sell", reason="trail", snr=snr_t)
            if spec.kind == "macd":
                m, s = row.get("macd"), row.get("macd_sig")
                mp, sp = row.get("macd_prev"), row.get("macd_sig_prev")
                if pd.notna(m) and pd.notna(s) and pd.notna(mp) and pd.notna(sp):
                    if float(mp) >= float(sp) and float(m) < float(s):
                        pending_exit = Pending(side="sell", reason="macd_cross", snr=snr_t)
            if spec.kind == "rsi":
                r = row.get("rsi")
                if pd.notna(r) and float(r) >= float(spec.rsi_ob):
                    pending_exit = Pending(side="sell", reason="rsi_ob", snr=snr_t)
            if spec.kind == "kd":
                k, d = row.get("k"), row.get("d")
                kp, dp = row.get("k_prev"), row.get("d_prev")
                if pd.notna(k) and pd.notna(d) and pd.notna(kp) and pd.notna(dp):
                    death = float(kp) >= float(dp) and float(k) < float(d)
                    if death or float(k) >= float(spec.kd_ob):
                        pending_exit = Pending(side="sell", reason="kd_exit", snr=snr_t)
            if spec.kind == "sma":
                f, s = row.get("sma_fast"), row.get("sma_slow")
                fp, sp = row.get("sma_fast_prev"), row.get("sma_slow_prev")
                if pd.notna(f) and pd.notna(s) and pd.notna(fp) and pd.notna(sp):
                    if float(fp) >= float(sp) and float(f) < float(s):
                        pending_exit = Pending(side="sell", reason="sma_cross", snr=snr_t)
            if spec.kind == "bb":
                c_px, up, lo, mid = row.get("Close"), row.get("bb_up"), row.get("bb_lo"), row.get("bb_mid")
                if pd.notna(c_px) and pd.notna(up) and pd.notna(lo) and pd.notna(mid):
                    mode = spec.bb_mode or "revert"
                    if mode == "break" and float(c_px) < float(mid):
                        pending_exit = Pending(side="sell", reason="bb_mid", snr=snr_t)
                    if mode != "break" and float(c_px) >= float(up):
                        pending_exit = Pending(side="sell", reason="bb_up", snr=snr_t)
            if pending_exit is not None:
                pending = pending_exit
        else:
            if spec.entry_signal(row):
                reason = spec.kind
                pending = Pending(side="buy", reason=reason, snr=snr_t)

    if pos.shares > 0 and len(bars) > 0:
        last = bars.index[-1]
        last_c = float(bars.iloc[-1]["Close"])
        pos, cash = _sell(
            pos, cash, last_c, last, ticker, name, "eod_force", last_c, trade_rows
        )
        if equity_pts and equity_pts[-1][0] == last:
            equity_pts[-1] = (last, cash)
        elif last >= start:
            equity_pts.append((last, cash))

    trades = pd.DataFrame(trade_rows)
    if equity_pts:
        eq = pd.Series({d: v for d, v in equity_pts}, name=ticker, dtype=float)
        eq.index = pd.to_datetime(eq.index)
        eq = eq[~eq.index.duplicated(keep="last")].sort_index()
    else:
        eq = pd.Series(dtype=float, name=ticker)

    return BacktestResult(
        ticker=ticker,
        name=name,
        strategy=spec.name,
        trades=trades,
        equity=eq,
        initial_capital=initial_capital,
    )


def run_universe(
    prices: dict[str, pd.DataFrame],
    spec: StrategySpec,
    initial_capital: float = INITIAL_CAPITAL,
    start_date: str | None = None,
    end_date: str | None = None,
    twii: pd.DataFrame | None = None,
) -> list[BacktestResult]:
    if twii is None:
        twii = prices.get(INDEX_TICKER)
    results = []
    for ticker, name in TICKERS.items():
        df = prices.get(ticker)
        if df is None or df.empty:
            results.append(
                BacktestResult(
                    ticker, name, spec.name,
                    pd.DataFrame(), pd.Series(dtype=float), initial_capital,
                    failed="missing",
                )
            )
            continue
        results.append(
            run_one(
                df, spec, ticker, name, initial_capital,
                start_date=start_date, end_date=end_date, twii=twii,
            )
        )
    return results
