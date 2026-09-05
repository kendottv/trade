"""Common TA curves from cached OHLC. No extra download. Not a broker."""
from __future__ import annotations

import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.astype(float).rolling(int(n), min_periods=int(n)).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.astype(float).ewm(span=int(n), adjust=False).mean()


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    c = close.astype(float)
    line = ema(c, fast) - ema(c, slow)
    sig = ema(line, signal)
    hist = line - sig
    return line, sig, hist


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.astype(float).diff()
    up = d.clip(lower=0).rolling(n, min_periods=n).mean()
    dn = (-d.clip(upper=0)).rolling(n, min_periods=n).mean()
    rs = up / dn.replace(0, pd.NA)
    return (100 - 100 / (1 + rs)).fillna(50)


def kd(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 9, k: int = 3, d: int = 3):
    h, l, c = high.astype(float), low.astype(float), close.astype(float)
    n, k, d = int(n), max(1, int(k)), max(1, int(d))
    ll = l.rolling(n, min_periods=n).min()
    hh = h.rolling(n, min_periods=n).max()
    den = (hh - ll).replace(0, float("nan"))
    rsv = ((c - ll) / den * 100).astype(float)
    kline = rsv.ewm(alpha=1 / k, adjust=False).mean()
    dline = kline.ewm(alpha=1 / d, adjust=False).mean()
    return kline, dline


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0):
    c = close.astype(float)
    mid = sma(c, n)
    sd = c.rolling(int(n), min_periods=int(n)).std()
    return mid, mid + float(k) * sd, mid - float(k) * sd


def pack_curves(df: pd.DataFrame, n: int = 132) -> dict:
    """Last n bars of SMA / MACD / RSI / KD. Uses cache only."""
    if df is None or df.empty or "Close" not in df.columns:
        return {"bars": [], "sma20": [], "sma60": [], "macd": [], "rsi": [], "kd": []}
    out = df.copy()
    out.index = pd.to_datetime(out.index).normalize()
    c = out["Close"]
    h = out["High"] if "High" in out.columns else c
    l = out["Low"] if "Low" in out.columns else c
    out["sma20"] = sma(c, 20)
    out["sma60"] = sma(c, 60)
    m, s, hist = macd(c)
    out["macd"], out["macd_sig"], out["macd_hist"] = m, s, hist
    out["rsi"] = rsi(c, 14)
    kline, dline = kd(h, l, c)
    out["k"], out["d"] = kline, dline
    view = out.tail(int(n) if n else 260)

    def pts(col):
        rows = []
        for ts, val in view[col].items():
            if pd.isna(val):
                continue
            rows.append({"time": pd.Timestamp(ts).strftime("%Y-%m-%d"), "value": float(val)})
        return rows

    bars = []
    for ts, row in view.iterrows():
        if pd.isna(row.get("Close")):
            continue
        bars.append({
            "time": pd.Timestamp(ts).strftime("%Y-%m-%d"),
            "open": float(row["Open"]) if "Open" in view.columns and pd.notna(row["Open"]) else float(row["Close"]),
            "high": float(row["High"]) if "High" in view.columns and pd.notna(row["High"]) else float(row["Close"]),
            "low": float(row["Low"]) if "Low" in view.columns and pd.notna(row["Low"]) else float(row["Close"]),
            "close": float(row["Close"]),
        })
    return {
        "bars": bars,
        "sma20": pts("sma20"),
        "sma60": pts("sma60"),
        "macd": pts("macd"),
        "macd_sig": pts("macd_sig"),
        "macd_hist": pts("macd_hist"),
        "rsi": pts("rsi"),
        "k": pts("k"),
        "d": pts("d"),
    }
