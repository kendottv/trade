"""Strategy implementations: CTA (A1/A2) and mean-reversion (B).

Daily processing order (mandatory, fix2 / AC-5 / AC-6):
1. Compute today's return using the position that existed BEFORE any fill today.
2. Execute pending fills at today's close (normal signals) AND forced sells
   (exclusion / true series end) at today's close.
3. Using today's close, generate normal signals and schedule fills for tomorrow's close.

Forced sells (AC-6 exceptions) happen at the last constituent / last-price day close,
after the day's return is earned. Normal mean-reversion and 10-day exits remain
t-signal → t+1-fill.

Price interruption = the price series has no more closes after today
(until the planned exit). Intermediate missing days are NOT series end.
"""
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .config import (
    CTA_MA_WINDOW,
    B_MA_SHORT,
    B_STD_MULT,
    B_MA_LONG,
    B_MAX_HOLD_DAYS,
    B_MAX_POSITIONS,
    B_WEIGHT_PER_POSITION,
    DEFAULT_PRINCIPAL_TWD,
)
from .costs import compute_side_cost


def _monthly_from_daily(daily_ret: pd.Series) -> pd.Series:
    if daily_ret.empty:
        return daily_ret
    monthly = (1 + daily_ret).resample("ME").prod() - 1
    monthly.name = daily_ret.name
    return monthly.dropna()


def _is_constituent(code: str, date: pd.Timestamp, membership: pd.DataFrame) -> bool:
    if membership.empty:
        return False
    d = pd.to_datetime(date)
    sub = membership[membership["code"] == str(code)]
    if sub.empty:
        return False
    mask = (sub["start_date"] <= d) & (sub["end_date"].isna() | (d < sub["end_date"]))
    return bool(mask.any())


def cta_signal(twii_close: pd.Series, window: int = CTA_MA_WINDOW) -> pd.Series:
    ma = twii_close.rolling(window, min_periods=window).mean()
    signal = (twii_close > ma).astype(float)
    signal = signal.where(ma.notna(), np.nan)
    return signal


def backtest_cta(
    twii_close: pd.Series,
    price_long: pd.Series,
    price_short: Optional[pd.Series],
    apply_costs: bool = False,
    principal: float = DEFAULT_PRINCIPAL_TWD,
    name: str = "CTA",
) -> pd.Series:
    idx = twii_close.index.intersection(price_long.index)
    if price_short is not None:
        idx = idx.intersection(price_short.index)
    idx = idx.sort_values()
    if len(idx) == 0:
        return pd.Series(dtype=float, name=name)

    tw = twii_close.reindex(idx)
    pl = price_long.reindex(idx)
    ps = price_short.reindex(idx) if price_short is not None else None

    signal = cta_signal(tw)
    strat_ret = pd.Series(0.0, index=idx, name=name)

    holdings = 0
    pending = None

    long_sym = "0050.TW"
    short_sym = "00632R.TW" if ps is not None else None

    for i, dt in enumerate(idx):
        if i > 0:
            r_long = float(pl.iloc[i] / pl.iloc[i - 1] - 1.0)
            if ps is not None:
                r_short = float(ps.iloc[i] / ps.iloc[i - 1] - 1.0)
            else:
                r_short = 0.0
            strat_ret.loc[dt] += holdings * r_long + (1 - holdings) * r_short

        if pending is not None:
            new_hold = pending
            if apply_costs and new_hold != holdings:
                if holdings == 1:
                    cost = compute_side_cost(principal, is_buy=False, symbol=long_sym)
                    strat_ret.loc[dt] -= cost / principal
                elif holdings == 0 and short_sym is not None:
                    cost = compute_side_cost(principal, is_buy=False, symbol=short_sym)
                    strat_ret.loc[dt] -= cost / principal
                if new_hold == 1:
                    cost = compute_side_cost(principal, is_buy=True, symbol=long_sym)
                    strat_ret.loc[dt] -= cost / principal
                elif new_hold == 0 and short_sym is not None:
                    cost = compute_side_cost(principal, is_buy=True, symbol=short_sym)
                    strat_ret.loc[dt] -= cost / principal
            holdings = new_hold
            pending = None

        sig = signal.loc[dt]
        if pd.notna(sig):
            desired = int(sig)
            if desired != holdings:
                pending = desired

    return strat_ret


def a1_monthly(
    twii_close: pd.Series,
    price_0050: pd.Series,
    apply_costs: bool = False,
    principal: float = DEFAULT_PRINCIPAL_TWD,
) -> pd.Series:
    daily = backtest_cta(twii_close, price_0050, None, apply_costs, principal, "A1")
    return _monthly_from_daily(daily)


def a2_monthly(
    twii_close: pd.Series,
    price_0050: pd.Series,
    price_00632r: pd.Series,
    apply_costs: bool = False,
    principal: float = DEFAULT_PRINCIPAL_TWD,
) -> pd.Series:
    daily = backtest_cta(twii_close, price_0050, price_00632r, apply_costs, principal, "A2")
    return _monthly_from_daily(daily)


def _compute_b_indicators(price: pd.Series) -> pd.DataFrame:
    ma20 = price.rolling(B_MA_SHORT, min_periods=B_MA_SHORT).mean()
    std20 = price.rolling(B_MA_SHORT, min_periods=B_MA_SHORT).std(ddof=1)
    ma200 = price.rolling(B_MA_LONG, min_periods=B_MA_LONG).mean()
    z = (price - ma20) / std20.replace(0, np.nan)
    return pd.DataFrame({
        "close": price,
        "ma20": ma20,
        "std20": std20,
        "ma200": ma200,
        "z": z,
    })


def compute_tradable_info(
    prices: Dict[str, pd.Series],
    membership: pd.DataFrame,
    trading_dates: pd.DatetimeIndex,
) -> Tuple[Dict[str, pd.Timestamp], Dict[str, str]]:
    trading_dates = pd.DatetimeIndex(trading_dates).sort_values()
    first: Dict[str, pd.Timestamp] = {}
    never: Dict[str, str] = {}
    all_codes = set(membership["code"].astype(str).unique()) | set(prices.keys())

    for code in sorted(all_codes):
        price = prices.get(code)
        if price is None or price.empty:
            never[code] = "無價格資料"
            continue
        price = price.sort_index()
        found = None
        for dt in trading_dates:
            if not _is_constituent(code, dt, membership):
                continue
            if dt not in price.index:
                continue
            n_hist = int((price.index <= dt).sum())
            if n_hist >= B_MA_LONG:
                found = dt
                break
        if found is not None:
            first[code] = found
        else:
            cons_days = [
                dt for dt in trading_dates
                if _is_constituent(code, dt, membership) and dt in price.index
            ]
            if not cons_days:
                never[code] = "在共同期間內從未成為成分股或無當日收盤價"
            else:
                max_hist = max(int((price.index <= dt).sum()) for dt in cons_days)
                if max_hist < B_MA_LONG:
                    never[code] = f"成分股期間內歷史收盤價不足 {B_MA_LONG} 日（最多 {max_hist} 日）"
                else:
                    never[code] = "未知原因"
    return first, never


def backtest_b(
    prices: Dict[str, pd.Series],
    membership: pd.DataFrame,
    trading_dates: pd.DatetimeIndex,
    apply_costs: bool = False,
    principal: float = DEFAULT_PRINCIPAL_TWD,
) -> Tuple[pd.Series, List[dict]]:
    """Event-driven mean-reversion back-test (AC-6).

    Forced exclusion sells execute at the last constituent day close.
    True series-end (no more prices after today) sells at the last available close.
    Intermediate missing prices are skipped (no return that day) but do not force a sell.
    """
    trading_dates = pd.DatetimeIndex(trading_dates).sort_values()
    if len(trading_dates) == 0 or not prices:
        return pd.Series(dtype=float, name="B"), []

    indicators: Dict[str, pd.DataFrame] = {}
    for code, ser in prices.items():
        if ser is not None and not ser.empty:
            indicators[code] = _compute_b_indicators(ser.astype(float).sort_index())

    dates = trading_dates
    holdings: Dict[str, dict] = {}
    pending_buys: List[str] = []
    pending_sells: List[str] = []
    events: List[dict] = []

    daily_ret = pd.Series(0.0, index=dates, name="B")
    date_list = list(dates)

    for i, dt in enumerate(date_list):
        prev = date_list[i - 1] if i > 0 else None
        next_dt = date_list[i + 1] if i + 1 < len(date_list) else None

        # 1. Earn today's return with positions held before this close
        #    (skip if no price today — intermediate gap)
        if prev is not None and holdings:
            for code in list(holdings.keys()):
                pser = prices.get(code)
                if pser is None or prev not in pser.index or dt not in pser.index:
                    continue
                r = float(pser.loc[dt] / pser.loc[prev] - 1.0)
                daily_ret.loc[dt] += B_WEIGHT_PER_POSITION * r

        # 2a. Forced sells at THIS close
        forced_today = []
        for code, info in list(holdings.items()):
            pser = prices.get(code)
            has_today = pser is not None and dt in pser.index
            # True series end: no more closes after today in the entire price series
            has_any_future_price = (
                pser is not None and len(pser.index[pser.index > dt]) > 0
            )
            will_be_cons_next = (
                next_dt is not None and _is_constituent(code, next_dt, membership)
            )
            # Exclusion: next calendar day is not constituent
            if has_today and not will_be_cons_next and next_dt is not None:
                forced_today.append((code, False))  # not a price event
            # True series end: today is the last price ever
            elif has_today and not has_any_future_price:
                forced_today.append((code, True))   # price interruption event

        for code, is_price_event in forced_today:
            if code in holdings:
                if apply_costs:
                    notional = principal * B_WEIGHT_PER_POSITION
                    cost = compute_side_cost(notional, is_buy=False, symbol=code)
                    daily_ret.loc[dt] -= cost / principal
                if is_price_event:
                    info = holdings[code]
                    remaining = max(0, B_MAX_HOLD_DAYS - info["holding_days"])
                    planned_idx = i + remaining
                    planned = date_list[planned_idx] if planned_idx < len(date_list) else None
                    events.append({
                        "code": code,
                        "last_price_date": dt,
                        "original_sell_date": planned,
                    })
                holdings.pop(code, None)

        # 2b. Normal pending fills (scheduled from previous close)
        for code in list(pending_sells):
            if code in holdings:
                if apply_costs:
                    notional = principal * B_WEIGHT_PER_POSITION
                    cost = compute_side_cost(notional, is_buy=False, symbol=code)
                    daily_ret.loc[dt] -= cost / principal
                holdings.pop(code, None)
        pending_sells = []

        free = B_MAX_POSITIONS - len(holdings)
        for code in pending_buys:
            if free <= 0:
                break
            if code in holdings:
                continue
            pser = prices.get(code)
            if (
                _is_constituent(code, dt, membership)
                and pser is not None
                and dt in pser.index
            ):
                holdings[code] = {"holding_days": 0}
                if apply_costs:
                    notional = principal * B_WEIGHT_PER_POSITION
                    cost = compute_side_cost(notional, is_buy=True, symbol=code)
                    daily_ret.loc[dt] -= cost / principal
                free -= 1
        pending_buys = []

        # Increment holding days
        for info in holdings.values():
            info["holding_days"] += 1

        # 3. Normal exit / entry signals for NEXT close
        for code, info in list(holdings.items()):
            pser = prices.get(code)
            has_today = pser is not None and dt in pser.index
            if not has_today or code not in indicators:
                continue
            ind = indicators[code]
            if dt not in ind.index:
                continue
            row = ind.loc[dt]
            if pd.isna(row["ma20"]):
                continue
            exit_mean = row["close"] >= row["ma20"]
            exit_time = info["holding_days"] >= B_MAX_HOLD_DAYS
            if exit_mean or exit_time:
                if code not in pending_sells:
                    pending_sells.append(code)

        free_slots = B_MAX_POSITIONS - len(holdings)
        if free_slots > 0:
            candidates = []
            for code, ind in indicators.items():
                if code in holdings or code in pending_buys or code in pending_sells:
                    continue
                if not _is_constituent(code, dt, membership):
                    continue
                pser = prices.get(code)
                if pser is None or dt not in pser.index:
                    continue
                if int((pser.index <= dt).sum()) < B_MA_LONG:
                    continue
                if dt not in ind.index:
                    continue
                row = ind.loc[dt]
                if pd.isna(row["ma20"]) or pd.isna(row["ma200"]) or pd.isna(row["std20"]):
                    continue
                if (row["close"] < row["ma20"] - B_STD_MULT * row["std20"]) and (
                    row["close"] > row["ma200"]
                ):
                    zval = float(row["z"]) if pd.notna(row["z"]) else 0.0
                    candidates.append((code, zval))
            candidates.sort(key=lambda x: (x[1], x[0]))
            for code, _ in candidates[:free_slots]:
                pending_buys.append(code)

    return daily_ret, events


def b_monthly(
    prices: Dict[str, pd.Series],
    membership: pd.DataFrame,
    trading_dates: pd.DatetimeIndex,
    apply_costs: bool = False,
    principal: float = DEFAULT_PRINCIPAL_TWD,
) -> pd.Series:
    daily, _ = backtest_b(prices, membership, trading_dates, apply_costs, principal)
    return _monthly_from_daily(daily)
