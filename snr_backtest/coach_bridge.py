r"""trade-coach 橋接：取代 trade 原本自己抓的新聞熱度（news_risk.py）。

用 trade-coach 自己的 venv 跑它的 tools（子程序），不共用套件、不讀任何 .env 內容。
強制 TRADE_COACH_DB 指向 test_trades.db，不碰正式 trades.db。
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

COACH = Path(os.environ.get("TRADE_COACH_DIR") or r"D:\trade-coach")
COACH_URL = "http://localhost:7870"
ROOT = Path(__file__).resolve().parent


def _py() -> str:
    p = COACH / ".venv" / "Scripts" / "python.exe"
    return str(p if p.exists() else "python")


def call(code: str, timeout: int = 120) -> dict:
    env = dict(os.environ, PYTHONIOENCODING="utf-8",
               TRADE_COACH_DB=str(COACH / "data" / "test_trades.db"))
    try:
        p = subprocess.run([_py(), "-c", code], cwd=str(COACH), capture_output=True, text=True,
                           encoding="utf-8", timeout=timeout, env=env)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    line = (p.stdout or "").strip().splitlines()
    try:
        return json.loads(line[-1])
    except Exception:
        return {"ok": False, "error": (p.stderr or "")[-400:]}


def news_for(codes: list[str]) -> dict:
    code = ("import json; from tools import news; "
            f"n=news.get_news_heat(held={json.dumps(codes)}, max_headlines=8); "
            "print(json.dumps(n, ensure_ascii=False, default=str))")
    return call(code)


def snapshot(codes: list[str]) -> dict:
    out = news_for(codes)
    d = ROOT / "paper_nn"
    d.mkdir(exist_ok=True)
    (d / "coach_news.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return out


if __name__ == "__main__":
    acct = json.loads((ROOT / "paper_nn" / "account.json").read_text(encoding="utf-8"))
    r = snapshot([p["ticker"] for p in acct.get("positions", [])] + ["6197"])
    print("ok" if "error" not in r else r)