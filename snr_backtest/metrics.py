"""Performance metrics from closed trades + daily equity.

Win/loss uses round-trip PnL after Taiwan costs. SNR stats use the buy-row
signal-time Kaufman efficiency ratio.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _f(x, default=0.0) -> float:
    try:
        if x is None or x == "" or (isinstance(x, float) and math.isnan(x)):
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def round_trips(trades: pd.DataFrame) -> pd.DataFrame:
    """Pair buy → sell into closed trades. SNR taken from the buy row."""
    if trades is None or trades.empty:
        return pd.DataFrame(
            columns=["ticker", "name", "entry_date", "exit_date", "reason",
                     "pnl", "ret", "snr", "win"]
        )
    rows = []
    buy = None
    for _, r in trades.iterrows():
        if r["action"] == "buy":
            buy = r
        elif r["action"] == "sell" and buy is not None:
            shares = _f(buy["shares"])
            buy_cost = shares * _f(buy["price"]) + _f(buy.get("commission"))
            sell_net = (
                _f(r["shares"]) * _f(r["price"])
                - _f(r.get("commission"))
                - _f(r.get("tax"))
            )
            pnl = sell_net - buy_cost
            ret = pnl / buy_cost if buy_cost > 0 else 0.0
            snr = _f(buy.get("snr"), default=float("nan"))
            rows.append(
                {
                    "ticker": buy["ticker"],
                    "name": buy["name"],
                    "entry_date": buy["date"],
                    "exit_date": r["date"],
                    "reason": r["reason"],
                    "pnl": pnl,
                    "ret": ret,
                    "snr": snr,
                    "win": pnl > 0,
                }
            )
            buy = None
    return pd.DataFrame(rows)


def max_drawdown(equity: pd.Series) -> float:
    if equity is None or equity.empty:
        return 0.0
    eq = equity.astype(float)
    peak = eq.cummax()
    dd = (eq - peak) / peak.replace(0, np.nan)
    val = dd.min()
    return float(val) if pd.notna(val) else 0.0


def cagr(equity: pd.Series, initial: float) -> float:
    if equity is None or equity.empty or initial <= 0:
        return 0.0
    final = float(equity.iloc[-1])
    if final <= 0:
        return -1.0
    days = (equity.index[-1] - equity.index[0]).days
    if days <= 0:
        return final / initial - 1.0
    return (final / initial) ** (365.25 / days) - 1.0


def exposure(trades: pd.DataFrame, equity: pd.Series) -> float:
    """Fraction of equity days with an open position (inferred from buy/sell)."""
    if equity is None or equity.empty:
        return 0.0
    held = pd.Series(0, index=equity.index, dtype=int)
    if trades is None or trades.empty:
        return 0.0
    t = trades.copy()
    t["date"] = pd.to_datetime(t["date"])
    pos = 0
    buys = {d: 1 for d in t.loc[t["action"] == "buy", "date"]}
    sells = {d: 1 for d in t.loc[t["action"] == "sell", "date"]}
    for d in held.index:
        if d in buys:
            pos = 1
        held.loc[d] = pos
        if d in sells:
            pos = 0
    return float(held.mean())


def summarize_one(result) -> dict:
    """One row of per-ticker summary. `result` is engine.BacktestResult."""
    trips = round_trips(result.trades)
    n = len(trips)
    wins = trips[trips["win"]] if n else trips
    losses = trips[~trips["win"]] if n else trips
    n_wins = int(len(wins))
    n_losses = int(len(losses))
    gross_win = float(wins["pnl"].sum()) if n_wins else 0.0
    gross_loss = float(losses["pnl"].sum()) if n_losses else 0.0  # negative
    if n_losses == 0:
        pf = math.inf if gross_win > 0 else 0.0
    else:
        pf = gross_win / abs(gross_loss) if gross_loss != 0 else math.inf

    eq = result.equity
    initial = result.initial_capital
    final = float(eq.iloc[-1]) if eq is not None and len(eq) else initial
    avg_snr_w = float(wins["snr"].mean()) if n_wins and wins["snr"].notna().any() else float("nan")
    avg_snr_l = float(losses["snr"].mean()) if n_losses and losses["snr"].notna().any() else float("nan")

    return {
        "ticker": result.ticker,
        "name": result.name,
        "trades": n,
        "n_wins": n_wins,
        "n_losses": n_losses,
        "win_rate": (n_wins / n) if n else 0.0,
        "avg_win": float(wins["ret"].mean()) if n_wins else 0.0,
        "avg_loss": float(losses["ret"].mean()) if n_losses else 0.0,
        "profit_factor": pf,
        "expectancy": float(trips["ret"].mean()) if n else 0.0,
        "expectancy_twd": float(trips["pnl"].mean()) if n else 0.0,
        "total_return": final / initial - 1.0 if initial else 0.0,
        "max_drawdown": max_drawdown(eq),
        "cagr": cagr(eq, initial),
        "final_equity": final,
        "exposure": exposure(result.trades, eq),
        "avg_snr_win": avg_snr_w,
        "avg_snr_loss": avg_snr_l,
        "failed": result.failed or "",
    }


def summarize_results(results: list) -> pd.DataFrame:
    rows = [summarize_one(r) for r in results]
    return pd.DataFrame(rows)


def combined_equity(results: list) -> pd.Series:
    """Sum of per-ticker 1M paper accounts (equal starting weight)."""
    series = [r.equity.rename(r.ticker) for r in results if r.equity is not None and len(r.equity)]
    if not series:
        return pd.Series(dtype=float, name="total")
    df = pd.concat(series, axis=1).sort_index()
    df = df.ffill()
    # Before a ticker's first bar, treat as sitting in cash (1M).
    for col in df.columns:
        initial = next((r.initial_capital for r in results if r.ticker == col), 1_000_000.0)
        df[col] = df[col].fillna(initial)
    total = df.sum(axis=1)
    total.name = "total"
    return total


def equity_frame(results: list) -> pd.DataFrame:
    series = [r.equity.rename(r.ticker) for r in results if r.equity is not None and len(r.equity)]
    if not series:
        return pd.DataFrame()
    df = pd.concat(series, axis=1).sort_index().ffill()
    for col in df.columns:
        initial = next((r.initial_capital for r in results if r.ticker == col), 1_000_000.0)
        df[col] = df[col].fillna(initial)
    df["total"] = df.sum(axis=1)
    return df


def combined_summary_row(results: list, summary: pd.DataFrame) -> dict:
    """Equal-weight combined account: 10 x 1M, trades concatenated."""
    all_trades = pd.concat(
        [r.trades for r in results if r.trades is not None and len(r.trades)],
        ignore_index=True,
    ) if any(r.trades is not None and len(r.trades) for r in results) else pd.DataFrame()
    total_eq = combined_equity(results)
    initial = sum(r.initial_capital for r in results) or 10_000_000.0
    fake = type("R", (), {})()
    fake.ticker = "EQUAL_WEIGHT"
    fake.name = "等權合計"
    fake.trades = all_trades
    fake.equity = total_eq
    fake.initial_capital = initial
    fake.failed = ""
    row = summarize_one(fake)
    return row


# --- equal-weight helpers (including 世紀-removed) ---

EW_TICKERS = {"EQUAL_WEIGHT", "EQUAL_WEIGHT_NO_5314"}


def equal_weight_row(
    results: list,
    exclude: set[str] | None = None,
    ticker: str = "EQUAL_WEIGHT",
    name: str = "等權合計",
) -> dict:
    """Equal-weight combined account over `results`, optionally dropping tickers."""
    subset = results if not exclude else [r for r in results if r.ticker not in exclude]
    if not subset:
        return {
            "ticker": ticker,
            "name": name,
            "trades": 0,
            "n_wins": 0,
            "n_losses": 0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "expectancy_twd": 0.0,
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "cagr": 0.0,
            "final_equity": 0.0,
            "exposure": 0.0,
            "avg_snr_win": float("nan"),
            "avg_snr_loss": float("nan"),
            "failed": "empty",
        }
    row = combined_summary_row(subset, pd.DataFrame())
    row["ticker"] = ticker
    row["name"] = name
    return row


def lottery_excluded_row(results: list, lottery: str = "5314.TWO") -> dict:
    return equal_weight_row(
        results,
        exclude={lottery},
        ticker="EQUAL_WEIGHT_NO_5314",
        name="等權合計（不含世紀）",
    )
