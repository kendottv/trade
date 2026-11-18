"""Low-volatility factor strategy (LV) research backtest.

Monthly rebalance: signal on last trading day t of month, fill at next trading day close.
Universe: TW50 point-in-time membership (left-closed right-open).
Selection: lowest 250-day daily-return std, equal weight top 10 (each 10%), industry cap 30% (max 3).
Insufficient names: remaining weight is cash.
Costs: fee 0.1425% (min 20 TWD), sell tax always 0.3%, slippage 0.1% each side, principal 1e6.

Note: if a stock is constituent on t and t+1 (selected) but not on t+2, it is bought at t+1 close
and forced-sold at t+2 close (one day after the last constituent trading day).
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from research.strategy_combo.config import DEFAULT_PRINCIPAL_TWD
from research.strategy_combo.strategies import _is_constituent


FEE_RATE = 0.001425
FEE_MIN_TWD = 20.0
TAX_RATE = 0.003  # always 0.3%
SLIPPAGE_RATE = 0.001
VOL_WINDOW = 250
N_SELECT = 10
INDUSTRY_CAP_PCT = 0.30  # max 3 out of 10
WEIGHT_PER = 1.0 / N_SELECT


def compute_side_cost_03(notional: float, is_buy: bool) -> float:
    """Absolute TWD cost for one side; sell tax always 0.3%."""
    if notional <= 0:
        return 0.0
    fee = max(notional * FEE_RATE, FEE_MIN_TWD)
    tax = 0.0 if is_buy else notional * TAX_RATE
    slippage = notional * SLIPPAGE_RATE
    return fee + tax + slippage


def load_industry_map(
    industry_csv: Path,
    delisted_csv: Path,
) -> Dict[str, str]:
    """Load code -> industry. industry.csv first, then delisted."""
    if not industry_csv.exists():
        raise FileNotFoundError(f"industry.csv not found: {industry_csv}")
    ind = pd.read_csv(industry_csv, encoding="utf-8", dtype={"code": str})
    ind["code"] = ind["code"].astype(str).str.strip()
    mapping = dict(zip(ind["code"], ind["industry"]))
    if delisted_csv.exists():
        d = pd.read_csv(delisted_csv, encoding="utf-8", dtype={"code": str})
        d["code"] = d["code"].astype(str).str.strip()
        for _, row in d.iterrows():
            c = str(row["code"]).strip()
            if c not in mapping:
                mapping[c] = str(row["industry"])
    return mapping


def check_all_codes_have_industry(
    membership: pd.DataFrame,
    industry_map: Dict[str, str],
) -> None:
    """Raise with all missing codes if any membership code has no industry."""
    codes = set(membership["code"].astype(str).str.strip().unique())
    missing = sorted(c for c in codes if c not in industry_map)
    if missing:
        raise RuntimeError(f"查不到產業別的代碼：{missing}")


def _eligible_on_date(
    code: str,
    t: pd.Timestamp,
    t_next: Optional[pd.Timestamp],
    price: pd.Series,
    membership: pd.DataFrame,
) -> bool:
    if price is None or price.empty or t not in price.index:
        return False
    if not _is_constituent(code, t, membership):
        return False
    if t_next is None or not _is_constituent(code, t_next, membership):
        return False
    hist = price[price.index <= t]
    if len(hist) < VOL_WINDOW + 1:  # need 250 returns => 251 prices
        return False
    return True


def select_lowvol(
    t: pd.Timestamp,
    t_next: Optional[pd.Timestamp],
    prices: Dict[str, pd.Series],
    membership: pd.DataFrame,
    industry_map: Dict[str, str],
) -> List[str]:
    """Return up to 10 codes, lowest vol, industry cap, ties by code.
    Check industry for ALL eligible before selecting. Raise if any missing.
    """
    eligible = []
    missing_ind = []
    for code, ser in prices.items():
        if not _eligible_on_date(code, t, t_next, ser, membership):
            continue
        hist = ser[ser.index <= t].tail(VOL_WINDOW + 1)
        rets = hist.pct_change().dropna()
        if len(rets) < VOL_WINDOW:
            continue
        vol = float(rets.std(ddof=1))
        ind = industry_map.get(code)
        if ind is None:
            missing_ind.append(code)
        else:
            eligible.append((vol, code, ind))
    if missing_ind:
        raise RuntimeError(f"查不到產業別的代碼：{sorted(set(missing_ind))}")
    if not eligible:
        return []
    eligible.sort(key=lambda x: (x[0], x[1]))
    selected: List[str] = []
    industry_count: Dict[str, int] = {}
    max_per = int(N_SELECT * INDUSTRY_CAP_PCT)  # 3
    for vol, code, ind in eligible:
        if len(selected) >= N_SELECT:
            break
        if industry_count.get(ind, 0) >= max_per:
            continue
        selected.append(code)
        industry_count[ind] = industry_count.get(ind, 0) + 1
    return selected


def backtest_lowvol(
    prices: Dict[str, pd.Series],
    membership: pd.DataFrame,
    industry_map: Dict[str, str],
    trading_dates: pd.DatetimeIndex,
    apply_costs: bool = False,
    principal: float = DEFAULT_PRINCIPAL_TWD,
) -> Tuple[pd.Series, pd.Series, List[dict], List[dict], pd.Series]:
    """Event-driven LV backtest.

    Returns daily returns, monthly returns, holdings log, forced events, traded_weight series.
    Each selected name gets weight 1/10; remaining is cash.
    Signal on month-end t, fill next trading day close.
    Forced sell if no longer constituent next day or series ends.
    traded_weight: absolute traded weight (buy + sell) on each day.
    Holdings log recorded only once per month on the month-end trading day (before fill).
    """
    trading_dates = pd.DatetimeIndex(trading_dates).sort_values()
    if len(trading_dates) == 0:
        empty = pd.Series(dtype=float, name="LV")
        return empty, empty, [], [], empty

    month_ends = []
    for per in trading_dates.to_period("M").unique():
        md = trading_dates[trading_dates.to_period("M") == per]
        if len(md):
            month_ends.append(md.max())
    month_ends = sorted(month_ends)

    date_list = list(trading_dates)
    holdings: Dict[str, float] = {}  # code -> weight
    pending_target: Optional[List[str]] = None
    daily_ret = pd.Series(0.0, index=trading_dates, name="LV")
    traded_weight = pd.Series(0.0, index=trading_dates, name="traded")
    holdings_log: List[dict] = []
    events: List[dict] = []

    for i, dt in enumerate(date_list):
        prev = date_list[i - 1] if i > 0 else None
        next_dt = date_list[i + 1] if i + 1 < len(date_list) else None

        # 1. Earn return with pre-fill holdings
        if prev is not None and holdings:
            for code, w in list(holdings.items()):
                ser = prices.get(code)
                if ser is None or prev not in ser.index or dt not in ser.index:
                    continue
                r = float(ser.loc[dt] / ser.loc[prev] - 1.0)
                daily_ret.loc[dt] += w * r

        # 2. Forced sells at this close
        forced = []
        for code in list(holdings.keys()):
            ser = prices.get(code)
            has_today = ser is not None and dt in ser.index
            has_future = ser is not None and len(ser.index[ser.index > dt]) > 0
            will_be_next = next_dt is not None and _is_constituent(code, next_dt, membership)
            if has_today and (not will_be_next or not has_future):
                forced.append(code)
        day_traded = 0.0
        for code in forced:
            if code in holdings:
                w = holdings.pop(code)
                day_traded += w
                if apply_costs:
                    notional = principal * w
                    cost = compute_side_cost_03(notional, is_buy=False)
                    daily_ret.loc[dt] -= cost / principal
                events.append({"code": code, "date": dt, "reason": "forced_sell"})

        # 3. Apply pending rebalance (scheduled from previous month-end)
        if pending_target is not None:
            new_codes = pending_target
            new_w_dict = {c: WEIGHT_PER for c in new_codes}
            old_codes = set(holdings.keys())
            new_set = set(new_codes)
            # sells
            for code in old_codes - new_set:
                w = holdings.pop(code)
                day_traded += w
                if apply_costs:
                    notional = principal * w
                    cost = compute_side_cost_03(notional, is_buy=False)
                    daily_ret.loc[dt] -= cost / principal
            # buys / weight changes
            for code in new_set:
                old_w = holdings.get(code, 0.0)
                delta = new_w_dict[code] - old_w
                if abs(delta) > 1e-9:
                    day_traded += abs(delta)
                    if apply_costs:
                        notional = principal * abs(delta)
                        is_buy = delta > 0
                        cost = compute_side_cost_03(notional, is_buy=is_buy)
                        daily_ret.loc[dt] -= cost / principal
                holdings[code] = new_w_dict[code]
            pending_target = None

        traded_weight.loc[dt] = day_traded

        # log holdings only once per month on month-end (before next fill)
        if dt in month_ends:
            holdings_log.append({
                "date": dt,
                "codes": list(holdings.keys()),
                "weights": dict(holdings),
                "n": len(holdings),
            })

        # 4. Generate signal if this is a month-end
        if dt in month_ends:
            target = select_lowvol(dt, next_dt, prices, membership, industry_map)
            current_set = set(holdings.keys())
            target_set = set(target)
            if target_set != current_set or any(abs(holdings.get(c, 0) - WEIGHT_PER) > 1e-9 for c in target_set):
                pending_target = target

    monthly = (1 + daily_ret).resample("ME").prod() - 1
    monthly.name = "LV"
    return daily_ret, monthly.dropna(), holdings_log, events, traded_weight


def lv_monthly(
    prices: Dict[str, pd.Series],
    membership: pd.DataFrame,
    industry_map: Dict[str, str],
    trading_dates: pd.DatetimeIndex,
    apply_costs: bool = False,
    principal: float = DEFAULT_PRINCIPAL_TWD,
) -> pd.Series:
    _, monthly, _, _, _ = backtest_lowvol(prices, membership, industry_map, trading_dates, apply_costs, principal)
    return monthly
