"""Live breakout_v2 + SNR_20. Matches config.BREAKOUT_V2_* (OOS winner).

Rules (look-ahead safe, bars through t only):
- SNR_20 Kaufman ER
- Buy at t close if close > max(high of prior 20 days)
  AND SNR_20 >= 0.40
  AND ^TWII close > ^TWII SMA 60
- Fill: next session open
- Exit: TP +25% / SL -20% (same-bar SL first)
        3 consecutive closes below prior 20-day low → next open
        Trail: once bar high is +12% vs fill, then close < prior 15-day low → next open
Does not trade. Paper layer queues next-open fills.
"""
from __future__ import annotations

import pandas as pd

from config import (
    BREAKOUT_LOOKBACK,
    BREAKOUT_SL,
    BREAKOUT_TIME_STOP_DAYS,
    BREAKOUT_TP,
    BREAKOUT_V2_SNR_MIN,
    BREAKOUT_V2_TRAIL_ARM,
    BREAKOUT_V2_TRAIL_LOOKBACK,
    BREAKOUT_V2_TWII_FILTER,
    SNR_N,
    TWII_SMA,
)

LOOKBACK = int(BREAKOUT_LOOKBACK)
SNR_MIN = float(BREAKOUT_V2_SNR_MIN)
TP = float(BREAKOUT_TP)
SL = float(BREAKOUT_SL)
TIME_STOP_DAYS = int(BREAKOUT_TIME_STOP_DAYS)
TRAIL_ARM = float(BREAKOUT_V2_TRAIL_ARM)
TRAIL_LOOKBACK = int(BREAKOUT_V2_TRAIL_LOOKBACK)
TWII_FILTER = bool(BREAKOUT_V2_TWII_FILTER)
TURNOVER_N = 20
STRATEGY_NAME = "breakout_v2"


def kaufman_snr(close: pd.Series, n: int = SNR_N) -> pd.Series:
    close = close.astype(float)
    step = close.diff().abs()
    denom = step.rolling(n, min_periods=n).sum()
    numer = (close - close.shift(n)).abs()
    snr = numer / denom
    snr = snr.where(denom > 0, 0.0)
    return snr.fillna(0.0)


def add_signal_columns(df: pd.DataFrame, twii: pd.DataFrame | None = None) -> pd.DataFrame:
    """Attach look-ahead-safe columns. prior_* exclude today (shift 1)."""
    out = df.copy()
    h, l, c = out["High"], out["Low"], out["Close"]
    n = LOOKBACK
    out["prior_high_20"] = h.shift(1).rolling(n, min_periods=n).max()
    out["prior_low_20"] = l.shift(1).rolling(n, min_periods=n).min()
    out["prior_low_15"] = l.shift(1).rolling(TRAIL_LOOKBACK, min_periods=TRAIL_LOOKBACK).min()
    out["snr_20"] = kaufman_snr(c, SNR_N)
    out["ret_20"] = c / c.shift(n) - 1.0
    out["turnover"] = c.astype(float) * out["Volume"].astype(float)
    out["avg_turnover_20"] = out["turnover"].rolling(TURNOVER_N, min_periods=TURNOVER_N).mean()
    if twii is not None and "Close" in twii.columns and len(twii):
        twii_c = twii["Close"].astype(float).reindex(out.index)
        twii_sma = twii_c.rolling(TWII_SMA, min_periods=TWII_SMA).mean()
        twii_ret = twii_c / twii_c.shift(n) - 1.0
        out["twii_close"] = twii_c
        out["twii_sma_60"] = twii_sma
        out["twii_ok"] = twii_c > twii_sma
        out["twii_ret_20"] = twii_ret
        out["rs_20"] = out["ret_20"] - twii_ret
    else:
        out["twii_close"] = pd.NA
        out["twii_sma_60"] = pd.NA
        out["twii_ok"] = True if not TWII_FILTER else False
        out["twii_ret_20"] = 0.0
        out["rs_20"] = out["ret_20"]
    return out


def is_entry(row: pd.Series) -> bool:
    """True if v2 breakout fires on this close (signal at t, fill t+1)."""
    prior = row.get("prior_high_20")
    snr = row.get("snr_20")
    close = row.get("Close")
    if prior is None or snr is None or close is None:
        return False
    if pd.isna(prior) or pd.isna(snr) or pd.isna(close):
        return False
    if float(close) <= float(prior):
        return False
    if float(snr) < SNR_MIN:
        return False
    if TWII_FILTER:
        ok = row.get("twii_ok")
        if ok is None or (isinstance(ok, float) and pd.isna(ok)) or not bool(ok):
            return False
    return True


def is_time_stop_bar(row: pd.Series) -> bool:
    prior_low = row.get("prior_low_20")
    close = row.get("Close")
    if prior_low is None or close is None:
        return False
    if pd.isna(prior_low) or pd.isna(close):
        return False
    return float(close) < float(prior_low)


def is_trail_bar(row: pd.Series, entry_price: float, trail_armed: bool) -> tuple[bool, bool]:
    """Return (armed_after_this_bar, trail_exit_today).

    Arm when this bar's high is >= entry * (1+12%). Once armed, close below
    prior 15-day low queues an exit (filled next open).
    """
    if entry_price <= 0:
        return trail_armed, False
    high = row.get("High")
    close = row.get("Close")
    prior15 = row.get("prior_low_15")
    armed = bool(trail_armed)
    if high is not None and not pd.isna(high):
        if float(high) >= entry_price * (1.0 + TRAIL_ARM):
            armed = True
    if not armed:
        return False, False
    if prior15 is None or close is None or pd.isna(prior15) or pd.isna(close):
        return True, False
    return True, float(close) < float(prior15)


def tp_sl_hit(entry_price: float, high: float, low: float, open_: float) -> tuple[str | None, float | None]:
    if entry_price <= 0:
        return None, None
    sl_px = entry_price * (1.0 - SL)
    tp_px = entry_price * (1.0 + TP)
    hit_sl = low <= sl_px or open_ <= sl_px
    hit_tp = high >= tp_px or open_ >= tp_px
    if hit_sl and hit_tp:
        return "sl", sl_px
    if hit_sl:
        return "sl", sl_px
    if hit_tp:
        return "tp", tp_px
    return None, None
