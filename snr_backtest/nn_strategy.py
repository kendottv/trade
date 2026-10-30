r"""NN 策略介面：只讀 trade_NN/out 的輸出檔，不在 Kendo 重新訓練。

主策略：TF-NN3 分數前 20 名等權、緩衝區 40、單一產業上限 30%、每月調倉。
路徑可用環境變數 NN_OUT_DIR 覆寫，預設 Desktop\trade_NN/out。
"""
from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NN_OUT = Path(os.environ.get("NN_OUT_DIR") or (ROOT.parent.parent / "trade_NN" / "out"))

STRATEGY = {
    "name": "nn_top20_buf40_ind30",
    "label": "NN 前 20 名等權（緩衝 40、產業上限 30%、每月調倉）",
    "top_n": 20, "buffer": 40, "industry_cap": 0.30,
    "buy_fee": 0.001425, "sell_fee": 0.001425, "sell_tax": 0.003, "slippage": 0.001,
}


def _read_csv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def target_files() -> list[Path]:
    return sorted(NN_OUT.glob("paper_target_*.csv"))


def latest_target() -> tuple[str, list[dict]] | None:
    files = target_files()
    if not files:
        return None
    p = files[-1]
    mon = re.search(r"paper_target_(\d{4}-\d{2})", p.name).group(1)
    rows = _read_csv(p)
    for r in rows:
        r["code"] = str(r["code"]).strip()
        r["weight"] = float(r.get("weight") or 0)
        r["close"] = float(r.get("close") or 0)
        r["rank"] = int(float(r.get("rank") or 0))
        r["score"] = float(r.get("score") or 0)
    return mon, rows


def watchlist() -> dict:
    p = NN_OUT / "watchlist_live.json"
    if not p.exists():
        return {"ok": False, "note": f"找不到 {p}"}
    raw = json.loads(p.read_text(encoding="utf-8"))
    recs = sorted(raw.get("records") or [], key=lambda r: r.get("rank", 10**9))
    for i, r in enumerate(recs, 1):
        r["watch_rank"] = i
    pos = next((r for r in recs if str(r.get("code")) == "6197"), None)
    return {"ok": True, "model": raw.get("model"), "target": raw.get("target"),
            "mon": recs[0]["mon"] if recs else None, "records": recs, "focus_6197": pos}


def preds_all() -> list[dict]:
    p = NN_OUT / "live_preds_all.csv"
    return _read_csv(p) if p.exists() else []