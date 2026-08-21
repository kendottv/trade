"""One-off: strategy vs buy-and-hold (TWII, EW universe, 2330)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from config import INDEX_TICKER
from universe import candidate_tickers, load_prices


def bh_index(df: pd.DataFrame, start: str, end: str) -> dict | None:
    c = df["Close"].astype(float)
    c = c[(c.index >= start) & (c.index <= end)].dropna()
    if len(c) < 10:
        return None
    eq = 1_000_000.0 * (c / float(c.iloc[0]))
    peak = eq.cummax()
    dd = eq / peak - 1.0
    years = (c.index[-1] - c.index[0]).days / 365.25
    endv = float(eq.iloc[-1])
    cagr = (endv / 1_000_000.0) ** (1.0 / years) - 1.0 if years > 0 else 0.0
    return {
        "end_eq": round(endv),
        "ret": endv / 1e6 - 1.0,
        "cagr": cagr,
        "maxdd": float(dd.min()),
        "maxdd_date": str(dd.idxmin().date()),
        "peak": round(float(eq.max())),
        "years": round(years, 2),
    }


def bh_equal_weight(prices: dict, start: str, end: str) -> dict | None:
    series: dict[str, pd.Series] = {}
    for t, df in prices.items():
        if t == INDEX_TICKER:
            continue
        c = df["Close"].astype(float)
        c = c[(c.index >= start) & (c.index <= end)].dropna()
        if len(c) < 60:
            continue
        series[t] = c
    if not series:
        return None
    cal = prices[INDEX_TICKER]["Close"]
    cal = cal[(cal.index >= start) & (cal.index <= end)].index
    first = cal[0]
    window = cal[:10]
    live = [t for t, c in series.items() if c.index.min() <= window[-1]]
    per = 1_000_000.0 / len(live)
    lots = {}
    for t in live:
        c = series[t]
        entry = float(c[c.index >= first].iloc[0])
        lots[t] = per / entry
    vals = []
    dates = []
    for d in cal:
        mv = 0.0
        for t, sh in lots.items():
            hist = series[t][series[t].index <= d]
            if len(hist):
                mv += sh * float(hist.iloc[-1])
        vals.append(mv)
        dates.append(d)
    eq = pd.Series(vals, index=pd.DatetimeIndex(dates))
    peak = eq.cummax()
    dd = eq / peak - 1.0
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    endv = float(eq.iloc[-1])
    cagr = (endv / 1_000_000.0) ** (1.0 / years) - 1.0 if years > 0 else 0.0
    return {
        "n": len(live),
        "end_eq": round(endv),
        "ret": endv / 1e6 - 1.0,
        "cagr": cagr,
        "maxdd": float(dd.min()),
        "maxdd_date": str(dd.idxmin().date()),
        "peak": round(float(eq.max())),
        "years": round(years, 2),
    }


def load_strat(folder: str) -> dict:
    eq = pd.read_csv(Path(folder) / "equity.csv", encoding="utf-8-sig")
    eq["date"] = pd.to_datetime(eq["date"])
    s = eq.set_index("date")["equity"].astype(float)
    peak = s.cummax()
    dd = s / peak - 1.0
    years = (s.index[-1] - s.index[0]).days / 365.25
    endv = float(s.iloc[-1])
    return {
        "end_eq": round(endv),
        "ret": endv / 1e6 - 1.0,
        "cagr": (endv / 1e6) ** (1.0 / years) - 1.0,
        "maxdd": float(dd.min()),
        "maxdd_date": str(dd.idxmin().date()),
        "peak": round(float(s.max())),
        "years": round(years, 2),
    }


def fmt(d: dict | None) -> str:
    if not d:
        return "n/a"
    return (
        f"end={d['end_eq']:,}  ret={d['ret']*100:.1f}%  "
        f"CAGR={d['cagr']*100:.1f}%  MDD={d['maxdd']*100:.1f}% "
        f"({d.get('maxdd_date','')})  peak={d.get('peak', 0):,}"
    )


def main() -> None:
    tickers = list(candidate_tickers().keys()) + [INDEX_TICKER]
    prices, failed = load_prices(tickers, force_download=False, end_date=None)
    print("failed", failed)
    windows = {
        "5y": ("2021-08-16", "2026-08-14", "paper/replay_5y"),
        "10y": ("2016-08-16", "2026-08-14", "paper/replay_10y"),
    }
    for lab, (a, b, folder) in windows.items():
        print("=" * 64, lab)
        print("STRATEGY ", fmt(load_strat(folder)))
        print("TWII     ", fmt(bh_index(prices[INDEX_TICKER], a, b)))
        print("EW pool  ", fmt(bh_equal_weight(prices, a, b)))
        print("2330     ", fmt(bh_index(prices["2330.TW"], a, b)))


if __name__ == "__main__":
    main()
