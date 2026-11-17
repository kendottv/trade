"""Performance metrics (AC-8).

Monthly formulas match the convention used in trade_NN/backtest_*.py:
- Sharpe = mean / std * sqrt(12), ddof=1, rf=0
- CAGR from cumprod
- MDD from monthly equity curve
Daily MDD is provided only as a reference for A and B.
"""
import numpy as np
import pandas as pd


def monthly_metrics(s: pd.Series) -> dict:
    """Compute annualized return, vol, Sharpe and MDD from a monthly return series.

    Parameters
    ----------
    s : pd.Series
        Monthly simple returns (e.g. 0.05 for +5%).

    Returns
    -------
    dict with keys: cagr_pct, ann_vol_pct, sharpe, mdd_pct, n_months
    """
    s = s.dropna()
    n = len(s)
    if n == 0:
        return {
            "cagr_pct": np.nan,
            "ann_vol_pct": np.nan,
            "sharpe": np.nan,
            "mdd_pct": np.nan,
            "n_months": 0,
        }

    c = (1 + s).cumprod()
    y = n / 12.0
    cagr_pct = (c.iloc[-1] ** (1 / y) - 1) * 100 if y > 0 else np.nan

    std = s.std()  # pandas default ddof=1
    sharpe = s.mean() / std * np.sqrt(12) if std > 0 else np.nan
    mdd_pct = ((c / c.cummax()) - 1).min() * 100
    ann_vol_pct = std * np.sqrt(12) * 100

    return {
        "cagr_pct": float(cagr_pct),
        "ann_vol_pct": float(ann_vol_pct),
        "sharpe": float(sharpe),
        "mdd_pct": float(mdd_pct),
        "n_months": n,
    }


def max_drawdown_pct(returns: pd.Series) -> float:
    """Maximum drawdown in percent from a return series (monthly or daily).

    Returns the most negative value (e.g. -20.69).
    """
    r = returns.dropna()
    if len(r) == 0:
        return np.nan
    equity = (1 + r).cumprod()
    dd = equity / equity.cummax() - 1
    return float(dd.min() * 100)


def daily_mdd_pct(daily_returns: pd.Series) -> float:
    """Reference daily-frequency maximum drawdown (percent)."""
    return max_drawdown_pct(daily_returns)
