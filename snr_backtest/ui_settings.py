"""Dashboard overlay for watchlist / strategy / news thresholds.

paper/ui_settings.json is the only file the panel writes.
Paper live, alerts, and news each start a new process, so they pick up
saves on the next 09:00 / 16:00 / 08:30 run — not mid-process.

Not a broker. Does not flatten live positions.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SETTINGS_PATH = ROOT / "paper" / "ui_settings.json"

TICKER_RE = re.compile(r"^\d{4}\.(TW|TWO)$")

STRATEGY_KEYS = (
    "BREAKOUT_V2_SNR_MIN",
    "BREAKOUT_LOOKBACK",
    "BREAKOUT_TP",
    "BREAKOUT_SL",
    "BREAKOUT_TIME_STOP_DAYS",
    "BREAKOUT_V2_TWII_FILTER",
    "BREAKOUT_V2_TRAIL",
    "BREAKOUT_V2_TRAIL_ARM",
    "BREAKOUT_V2_TRAIL_LOOKBACK",
    "TWII_SMA",
    "PAPER_MAX_WEIGHT",
    "PAPER_LOT_SIZE",
    "MAX_POSITIONS",
)




def load_raw() -> dict:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_raw(data: dict) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    tmp = SETTINGS_PATH.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(SETTINGS_PATH)


def coerce(default, value):
    if isinstance(default, bool):
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)
    if isinstance(default, int) and not isinstance(default, bool):
        return int(value)
    if isinstance(default, float):
        return float(value)
    return value


def load_watchlist() -> dict[str, str] | None:
    """None = use code defaults. Empty dict is treated as missing."""
    raw = load_raw().get("watchlist")
    if not isinstance(raw, dict) or not raw:
        return None
    out: dict[str, str] = {}
    for ticker, name in raw.items():
        t = str(ticker).strip().upper()
        if not TICKER_RE.match(t):
            continue
        n = str(name).strip() if name is not None else t
        out[t] = n or t
    return out or None


def effective_strategy(defaults: dict) -> dict:
    out = dict(defaults)
    overlay = load_strategy_overlay()
    for key, value in overlay.items():
        if key not in defaults:
            continue
        try:
            out[key] = coerce(defaults[key], value)
        except (TypeError, ValueError):
            continue
    return out


def load_strategy_overlay() -> dict:
    raw = load_raw().get("strategy")
    if not isinstance(raw, dict):
        return {}
    return {k: raw[k] for k in STRATEGY_KEYS if k in raw}


def apply_strategy_to_module(g: dict, defaults: dict) -> None:
    overlay = load_strategy_overlay()
    for key, value in overlay.items():
        if key not in defaults:
            continue
        try:
            g[key] = coerce(defaults[key], value)
        except (TypeError, ValueError):
            continue


def save_watchlist(watchlist: dict[str, str]) -> None:
    data = load_raw()
    cleaned: dict[str, str] = {}
    try:
        from universe import BANK_TICKERS
    except Exception:
        BANK_TICKERS = {}
    for ticker, name in watchlist.items():
        t = str(ticker).strip().upper()
        if not TICKER_RE.match(t):
            raise ValueError(f"代號格式不對：{ticker}（要像 2330.TW / 5314.TWO）")
        if t in BANK_TICKERS:
            continue
        cleaned[t] = (str(name).strip() or t)
    if not cleaned:
        raise ValueError("監看名單不能是空的")
    data["watchlist"] = cleaned
    save_raw(data)


def save_strategy(strategy: dict) -> None:
    data = load_raw()
    data["strategy"] = {k: strategy[k] for k in STRATEGY_KEYS if k in strategy}
    save_raw(data)


def reset_all() -> None:
    if SETTINGS_PATH.exists():
        SETTINGS_PATH.unlink()
