r"""代號→公司名稱（單一來源：trade_NN\data\stock_names.csv，由 build_stock_names.py 產生：永豐合約為主、TWSE/TPEx 公開清單備援）。"""
from __future__ import annotations

import csv
import subprocess
import sys
import time
from pathlib import Path

CSV = Path(r"C:\Users\AUSER\Desktop\trade_NN\data\stock_names.csv")
MISSING = "(名稱待查)"
_cache: dict = {"mtime": None, "map": {}}


def names() -> dict:
    try:
        m = CSV.stat().st_mtime
    except OSError:
        return {}
    if _cache["mtime"] != m:
        with CSV.open(encoding="utf-8-sig") as f:
            _cache["map"] = {r["code"]: r["name"] for r in csv.DictReader(f) if r.get("name")}
        _cache["mtime"] = m
    return _cache["map"]


def name(code) -> str | None:
    return names().get(str(code).strip())


def label(code) -> str:
    c = str(code).strip()
    n = name(c)
    return f"{c} {n}" if n else f"{c} {MISSING}"


def refresh_if_old(max_age_days: float = 7) -> bool:
    """map 不存在或超過 max_age_days 就重建（另開程序跑，失敗保留舊檔）。"""
    try:
        if CSV.exists() and time.time() - CSV.stat().st_mtime < max_age_days * 86400:
            return False
    except OSError:
        pass
    r = subprocess.run([sys.executable, str(Path(__file__).with_name("build_stock_names.py"))],
                       capture_output=True, timeout=600)
    return r.returncode == 0
