"""Cross-asset momentum (XA) research backtest.

Universe: 0050, 00679B, 00635U (+ cash).
Momentum: average of 3/6/12-month total returns on month-end (last trading day) adjusted prices.
Top 2, 50% each; momentum <= 0 becomes cash (return 0).
Signal on month-end t, fill next trading day close. Only trade changed portion.
Need 12 full months of month-end prices before first signal.
First performance month is the month after first signal fill.
Costs: same as LV (always 0.3% sell tax).
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from research.strategy_combo.config import DEFAULT_PRINCIPAL_TWD
from research.strategy_combo.lowvol import compute_side_cost_03


def filter_pre_listing(df: pd.DataFrame, listing_date: pd.Timestamp) -> Tuple[pd.DataFrame, int]:
    """Drop rows strictly before listing_date. Return filtered df and n dropped."""
    if df.empty:
        return df, 0
    before = df.index < listing_date
    n_drop = int(before.sum())
    return df.loc[~before].copy(), n_drop


def build_month_end_prices(
    prices: Dict[str, pd.Series],
    trading_dates: pd.DatetimeIndex,
) -> Dict[str, pd.Series]:
    """Month-end price = close on or before last trading day of that month. Index = that trading day."""
    trading_dates = pd.DatetimeIndex(trading_dates).sort_values()
    month_ends = []
    for per in trading_dates.to_period("M").unique():
        md = trading_dates[trading_dates.to_period("M") == per]
        if len(md):
            month_ends.append(md.max())
    month_end_px: Dict[str, pd.Series] = {}
    for code, ser in prices.items():
        if ser is None or ser.empty:
            continue
        ser = ser.sort_index()
        vals = []
        idx = []
        for me in month_ends:
            avail = ser.index[ser.index <= me]
            if len(avail) == 0:
                continue
            last = avail.max()
            vals.append(float(ser.loc[last]))
            idx.append(me)
        if idx:
            month_end_px[code] = pd.Series(vals, index=pd.DatetimeIndex(idx))
    return month_end_px


def compute_momentum(month_end_prices: pd.Series, t: pd.Timestamp) -> Optional[float]:
    """Average of 3/6/12-month total returns ending at t. None if insufficient history."""
    if t not in month_end_prices.index:
        return None
    idx = month_end_prices.index
    loc = idx.get_loc(t)
    if isinstance(loc, slice):
        loc = loc.stop - 1
    if loc < 12:
        return None
    p_t = float(month_end_prices.iloc[loc])
    rets = []
    for m in (3, 6, 12):
        p_past = float(month_end_prices.iloc[loc - m])
        if p_past <= 0:
            return None
        rets.append(p_t / p_past - 1.0)
    return float(np.mean(rets))


def select_xa(
    t: pd.Timestamp,
    month_end_px: Dict[str, pd.Series],
) -> Dict[str, float]:
    """Return {code: weight} for top 2 (or cash). Ties by code. Weight 0.5 or 0 if mom<=0."""
    moms = []
    for code, ser in month_end_px.items():
        mom = compute_momentum(ser, t)
        if mom is None:
            continue
        moms.append((mom, code))
    if len(moms) < 2:
        return {}
    moms.sort(key=lambda x: (-x[0], x[1]))  # highest mom first, then code
    top2 = moms[:2]
    weights: Dict[str, float] = {}
    for mom, code in top2:
        if mom > 0:
            weights[code] = 0.5
        else:
            weights[code] = 0.0  # cash slot
    return weights


def backtest_xa(
    prices: Dict[str, pd.Series],
    listing_dates: Dict[str, pd.Timestamp],
    trading_dates: pd.DatetimeIndex,
    apply_costs: bool = False,
    principal: float = DEFAULT_PRINCIPAL_TWD,
    end_limit: Optional[pd.Timestamp] = None,
) -> Tuple[pd.Series, pd.Series, List[dict], Dict[str, int], Optional[pd.Timestamp], pd.Series]:
    """XA event-driven backtest.

    Returns daily, monthly (only from first performance month), holdings log,
    holding months count (within performance period up to end_limit), first_performance_month, traded_weight.
    Months before first performance are absent from monthly series.
    Holding-month counting uses period (year-month) comparison so the first performance
    month is included even when its calendar month-end is not a trading day.
    """
    trading_dates = pd.DatetimeIndex(trading_dates).sort_values()
    if end_limit is not None:
        trading_dates = trading_dates[trading_dates <= end_limit]
    month_end_px = build_month_end_prices(prices, trading_dates)

    month_ends = []
    for per in trading_dates.to_period("M").unique():
        md = trading_dates[trading_dates.to_period("M") == per]
        if len(md):
            month_ends.append(md.max())
    month_ends = sorted(month_ends)

    date_list = list(trading_dates)
    holdings: Dict[str, float] = {}
    pending_target: Optional[Dict[str, float]] = None
    daily_ret = pd.Series(0.0, index=trading_dates, name="XA")
    traded_weight = pd.Series(0.0, index=trading_dates, name="traded")
    holdings_log: List[dict] = []
    hold_months: Dict[str, int] = {c: 0 for c in prices}

    first_signal_month: Optional[pd.Timestamp] = None
    for me in month_ends:
        if all(compute_momentum(month_end_px.get(c, pd.Series(dtype=float)), me) is not None for c in month_end_px):
            first_signal_month = me
            break

    first_performance_month: Optional[pd.Timestamp] = None
    if first_signal_month is not None:
        next_per = (first_signal_month.to_period("M") + 1).to_timestamp("M")
        after = [d for d in trading_dates if d > first_signal_month]
        if after:
            first_perf_day = after[0]
            first_performance_month = first_perf_day.to_period("M").to_timestamp("M")

    for i, dt in enumerate(date_list):
        prev = date_list[i - 1] if i > 0 else None

        # 1. Earn return
        if prev is not None and holdings:
            for code, w in list(holdings.items()):
                if w <= 0:
                    continue
                ser = prices.get(code)
                if ser is None or prev not in ser.index or dt not in ser.index:
                    continue
                r = float(ser.loc[dt] / ser.loc[prev] - 1.0)
                daily_ret.loc[dt] += w * r

        # 2. Apply pending rebalance
        day_traded = 0.0
        if pending_target is not None:
            new_w = pending_target
            old_codes = set(holdings.keys())
            new_codes = set(new_w.keys())
            all_codes = old_codes | new_codes
            for code in all_codes:
                old = holdings.get(code, 0.0)
                new = new_w.get(code, 0.0)
                delta = new - old
                if abs(delta) > 1e-9:
                    day_traded += abs(delta)
                    if apply_costs:
                        notional = principal * abs(delta)
                        cost = compute_side_cost_03(notional, is_buy=delta > 0)
                        daily_ret.loc[dt] -= cost / principal
            holdings = {c: w for c, w in new_w.items() if w > 0}
            pending_target = None

        traded_weight.loc[dt] = day_traded

        if dt in month_ends:
            holdings_log.append({
                "date": dt,
                "weights": dict(holdings),
                "n": sum(1 for w in holdings.values() if w > 0),
            })
            if first_performance_month is not None and dt.to_period("M") >= first_performance_month.to_period("M"):
                if end_limit is None or dt <= end_limit:
                    for c, w in holdings.items():
                        if w > 0:
                            hold_months[c] = hold_months.get(c, 0) + 1

            # generate next signal only after enough history
            if first_signal_month is not None and dt >= first_signal_month:
                target = select_xa(dt, month_end_px)
                if set(target.keys()) != set(holdings.keys()) or any(
                    abs(holdings.get(c, 0) - target.get(c, 0)) > 1e-9 for c in set(target) | set(holdings)
                ):
                    pending_target = target

    # monthly only from first performance month onward
    full_monthly = (1 + daily_ret).resample("ME").prod() - 1
    if first_performance_month is not None:
        monthly = full_monthly.loc[first_performance_month:]
    else:
        monthly = pd.Series(dtype=float, name="XA")
    monthly.name = "XA"
    return daily_ret, monthly.dropna(), holdings_log, hold_months, first_performance_month, traded_weight


def a1_daily_03(
    twii_close: pd.Series,
    price_0050: pd.Series,
    apply_costs: bool = False,
    principal: float = DEFAULT_PRINCIPAL_TWD,
) -> pd.Series:
    """A1 daily returns with always-0.3% sell tax (no short)."""
    idx = twii_close.index.intersection(price_0050.index).sort_values()
    if len(idx) == 0:
        return pd.Series(dtype=float, name="A1")
    tw = twii_close.reindex(idx)
    pl = price_0050.reindex(idx)
    from research.strategy_combo.strategies import cta_signal
    signal = cta_signal(tw)
    strat_ret = pd.Series(0.0, index=idx, name="A1")
    holdings = 0
    pending = None
    for i, dt in enumerate(idx):
        if i > 0:
            r_long = float(pl.iloc[i] / pl.iloc[i - 1] - 1.0)
            strat_ret.loc[dt] += holdings * r_long
        if pending is not None:
            new_hold = pending
            if apply_costs and new_hold != holdings:
                if holdings == 1:
                    cost = compute_side_cost_03(principal, is_buy=False)
                    strat_ret.loc[dt] -= cost / principal
                if new_hold == 1:
                    cost = compute_side_cost_03(principal, is_buy=True)
                    strat_ret.loc[dt] -= cost / principal
            holdings = new_hold
            pending = None
        sig = signal.loc[dt]
        if pd.notna(sig):
            desired = int(sig)
            if desired != holdings:
                pending = desired
    return strat_ret


def a1_monthly_03(
    twii_close: pd.Series,
    price_0050: pd.Series,
    apply_costs: bool = False,
    principal: float = DEFAULT_PRINCIPAL_TWD,
) -> pd.Series:
    """A1 monthly from the 0.3% daily series."""
    daily = a1_daily_03(twii_close, price_0050, apply_costs, principal)
    monthly = (1 + daily).resample("ME").prod() - 1
    monthly.name = "A1"
    return monthly.dropna()
