"""Portfolio construction and weight scans (AC-11).

All combinations use monthly returns after risk scaling.
Monthly rebalancing is implicit: each month's return is the weighted sum.
Weights always sum to 1.
"""
from typing import Dict, List

import numpy as np
import pandas as pd

from .metrics import monthly_metrics


def _align(*series: pd.Series) -> pd.DataFrame:
    df = pd.concat(series, axis=1, join="inner")
    return df.dropna()


def equal_weight(series_list: List[pd.Series], name: str) -> pd.Series:
    """Equal-weight monthly return of the given series (weights sum to 1)."""
    df = _align(*series_list)
    if df.empty:
        return pd.Series(dtype=float, name=name)
    n = df.shape[1]
    w = 1.0 / n
    combo = (df * w).sum(axis=1)
    combo.name = name
    return combo


def two_strategy_scan(
    nn3: pd.Series,
    other: pd.Series,
    other_name: str,
    step: float = 0.1,
) -> Dict[str, pd.Series]:
    """Scan NN3 weight from 0 to 1 in steps; the remainder goes to `other`.

    Every generated series uses weights that sum to 1.
    """
    df = _align(nn3, other)
    if df.empty:
        return {}
    results = {}
    weights = np.round(np.arange(0.0, 1.0 + step / 2, step), 10)
    for w_nn in weights:
        w_nn = float(np.round(w_nn, 2))
        w_ot = float(np.round(1.0 - w_nn, 2))
        label = f"NN3_{int(round(w_nn*100))}_{other_name}_{int(round(w_ot*100))}"
        combo = df.iloc[:, 0] * w_nn + df.iloc[:, 1] * w_ot
        combo.name = label
        results[label] = combo
    return results


def three_strategy_scan(
    nn3: pd.Series,
    a: pd.Series,
    b: pd.Series,
    a_name: str,
    step: float = 0.1,
) -> Dict[str, pd.Series]:
    """Grid search over three weights in 10% steps that sum to 1."""
    df = _align(nn3, a, b)
    if df.empty:
        return {}
    results = {}
    grid = np.round(np.arange(0.0, 1.0 + step / 2, step), 10)
    for w1 in grid:
        for w2 in grid:
            w3 = 1.0 - w1 - w2
            if w3 < -1e-9 or w3 > 1.0 + 1e-9:
                continue
            w1r = float(np.round(w1, 2))
            w2r = float(np.round(w2, 2))
            w3r = float(np.round(w3, 2))
            # re-normalize tiny float error
            s = w1r + w2r + w3r
            if abs(s - 1.0) > 1e-9:
                w3r = 1.0 - w1r - w2r
            label = f"NN3_{int(round(w1r*100))}_{a_name}_{int(round(w2r*100))}_B_{int(round(w3r*100))}"
            combo = df.iloc[:, 0] * w1r + df.iloc[:, 1] * w2r + df.iloc[:, 2] * w3r
            combo.name = label
            results[label] = combo
    return results


def summarize(series_dict: Dict[str, pd.Series]) -> pd.DataFrame:
    """Compute metrics for every series in the dict and return a DataFrame."""
    rows = []
    for name, s in series_dict.items():
        m = monthly_metrics(s)
        m["name"] = name
        rows.append(m)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("name")
