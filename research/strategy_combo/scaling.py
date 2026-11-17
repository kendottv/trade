"""Risk scaling so that a strategy's MDD matches a target (AC-10).

The scale factor is applied to the monthly return series. Because leverage
changes the path of the equity curve, a binary search is used. The factor
is computed on the full common period (look-ahead acknowledged in the report).
"""
import numpy as np
import pandas as pd

from .metrics import max_drawdown_pct


def find_scale_factor(returns: pd.Series, target_mdd_pct: float, tol: float = 0.05) -> float:
    """Find k such that MDD of (k * returns) is within tol percentage points of target."""
    r = returns.dropna()
    if len(r) == 0 or np.isnan(target_mdd_pct):
        return 1.0

    if target_mdd_pct >= 0:
        return 1.0

    def mdd_of(k: float) -> float:
        return max_drawdown_pct(k * r)

    low, high = 0.01, 10.0
    mdd_low = mdd_of(low)
    mdd_high = mdd_of(high)

    if mdd_high > target_mdd_pct:
        return high
    if mdd_low < target_mdd_pct:
        return low

    for _ in range(40):
        mid = (low + high) / 2.0
        mdd_mid = mdd_of(mid)
        if abs(mdd_mid - target_mdd_pct) <= tol:
            return mid
        if mdd_mid > target_mdd_pct:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def scale_returns(returns: pd.Series, target_mdd_pct: float) -> tuple[pd.Series, float]:
    """Return the scaled monthly return series and the factor used."""
    k = find_scale_factor(returns, target_mdd_pct)
    scaled = (k * returns).rename(getattr(returns, "name", None))
    return scaled, k
