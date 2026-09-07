# -*- coding: utf-8 -*-
"""TWSE 三大法人日彙總（BFI82U）— 免費公開資料，不是券商、不成交。

抓市場整體外資／投信／自營買賣超金額，快取到 paper/institutional.json，
並 append paper/institutional_journal.csv。不寫入、不改動 paper/account.json。
Shioaji 不提供此資料，請勿改用券商 API。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import ROOT

TAIPEI = timezone(timedelta(hours=8))
PAPER = ROOT / "paper"
CACHE_PATH = PAPER / "institutional.json"
JOURNAL_PATH = PAPER / "institutional_journal.csv"
STAMP_PATH = PAPER / "last_institutional.txt"

UA = "Mozilla/5.0 (compatible; TWPaperInstitutional/1.0)"
BFI82U = "https://www.twse.com.tw/rwd/zh/fund/BFI82U"

JOURNAL_COLS = [
    "logged_at",
    "date",
    "foreign_net",
    "foreign_net_yi",
    "trust_net",
    "trust_net_yi",
    "dealer_net",
    "dealer_net_yi",
    "dealer_prop_net",
    "dealer_hedge_net",
    "total_net",
    "total_net_yi",
    "source",
    "ok",
    "note",
]

YI = 100_000_000.0  # 1 億元


def _now_taipei() -> datetime:
    return datetime.now(TAIPEI)


def _now_iso() -> str:
    return _now_taipei().strftime("%Y-%m-%d %H:%M:%S")


def parse_amount(val) -> int | None:
    if val is None:
        return None
    s = str(val).strip().replace(",", "").replace("，", "")
    if s in ("", "-", "—", "N/A", "null"):
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    try:
        n = int(float(s))
    except (TypeError, ValueError):
        return None
    return -n if neg else n


def to_yi(n: int | None, digits: int = 2) -> float | None:
    if n is None:
        return None
    return round(n / YI, digits)


def _http_get(url: str, retries: int = 3, timeout: float = 25.0) -> str:
    last_err: Exception | None = None
    for i in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": UA,
                    "Accept": "application/json,text/plain,*/*",
                    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            for enc in ("utf-8-sig", "utf-8", "big5", "cp950"):
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    continue
            return raw.decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_err = exc
            time.sleep(0.8 * (i + 1))
    raise RuntimeError(f"TWSE fetch failed: {last_err}")


def fetch_bfi82u(day_yyyymmdd: str) -> dict:
    """Return raw TWSE JSON for one calendar day (may be empty on holidays)."""
    url = (
        f"{BFI82U}?response=json&dayDate={day_yyyymmdd}&type=day"
        f"&_={int(time.time() * 1000)}"
    )
    text = _http_get(url)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise RuntimeError("TWSE response not a JSON object")
    return data


def _match_row(name: str, *needles: str) -> bool:
    n = name.replace(" ", "")
    return all(nd in n for nd in needles)


def _row_payload(name: str, buy, sell, net) -> dict:
    b = parse_amount(buy)
    s = parse_amount(sell)
    n = parse_amount(net)
    if n is None and b is not None and s is not None:
        n = b - s
    return {
        "name": name,
        "buy": b,
        "sell": s,
        "net": n,
        "net_yi": to_yi(n),
    }


def parse_bfi82u(data: dict, day_yyyymmdd: str) -> dict | None:
    """Normalize BFI82U into panel-friendly payload. None if no usable rows."""
    stat = str(data.get("stat") or "")
    rows_raw = data.get("data") or []
    if stat and stat not in ("OK", "ok") and not rows_raw:
        return None
    if not rows_raw:
        return None

    by: dict[str, dict] = {}
    ordered = []
    for row in rows_raw:
        if not isinstance(row, (list, tuple)) or len(row) < 4:
            continue
        name = str(row[0]).strip()
        payload = _row_payload(name, row[1], row[2], row[3])
        ordered.append(payload)
        by[name] = payload

    foreign = None
    foreign_dealer = None
    trust = None
    dealer_prop = None
    dealer_hedge = None
    total = None

    for name, payload in by.items():
        n = name.replace(" ", "")
        if n == "外資自營商" or (n.startswith("外資自營") and "不含" not in n):
            foreign_dealer = payload
        elif "外資及陸資" in n:
            foreign = payload
        elif n == "投信" or (n.startswith("投信") and "合計" not in n):
            trust = payload
        elif "自營商" in n and "自行" in n:
            dealer_prop = payload
        elif "自營商" in n and "避險" in n:
            dealer_hedge = payload
        elif n in ("合計", "總計"):
            total = payload

    if foreign is None:
        for name, payload in by.items():
            n = name.replace(" ", "")
            if "外資" in n and n != "外資自營商" and not n.startswith("外資自營"):
                foreign = payload
                break

    dealer_net = None
    if dealer_prop or dealer_hedge:
        n1 = (dealer_prop or {}).get("net")
        n2 = (dealer_hedge or {}).get("net")
        if n1 is not None or n2 is not None:
            dealer_net = (n1 or 0) + (n2 or 0)
    dealer = {
        "name": "自營商(自行+避險)",
        "buy": None,
        "sell": None,
        "net": dealer_net,
        "net_yi": to_yi(dealer_net),
        "proprietary": dealer_prop,
        "hedge": dealer_hedge,
    }
    if dealer_prop and dealer_hedge:
        b1, b2 = dealer_prop.get("buy"), dealer_hedge.get("buy")
        s1, s2 = dealer_prop.get("sell"), dealer_hedge.get("sell")
        if b1 is not None and b2 is not None:
            dealer["buy"] = b1 + b2
        if s1 is not None and s2 is not None:
            dealer["sell"] = s1 + s2

    date_hyphen = f"{day_yyyymmdd[:4]}-{day_yyyymmdd[4:6]}-{day_yyyymmdd[6:8]}"
    twse_date = str(data.get("date") or day_yyyymmdd)
    if len(twse_date) == 8 and twse_date.isdigit():
        date_hyphen = f"{twse_date[:4]}-{twse_date[4:6]}-{twse_date[6:8]}"

    return {
        "ok": True,
        "date": date_hyphen,
        "day_date": day_yyyymmdd if len(twse_date) != 8 else twse_date,
        "source": "TWSE",
        "endpoint": "BFI82U",
        "unit": "元",
        "display_unit": "億",
        "title": str(data.get("title") or "三大法人買賣金額統計表"),
        "updated_at": _now_iso(),
        "foreign": foreign,
        "trust": trust,
        "dealer": dealer,
        "dealer_proprietary": dealer_prop,
        "dealer_hedge": dealer_hedge,
        "foreign_dealer": foreign_dealer,
        "total": total,
        "rows": ordered,
        "note": "證交所 BFI82U 日彙總；金額為元，面板以億顯示。不成交。",
    }


def empty_payload(note: str, day_yyyymmdd: str | None = None) -> dict:
    d = day_yyyymmdd or _now_taipei().strftime("%Y%m%d")
    return {
        "ok": False,
        "date": f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else "",
        "day_date": d,
        "source": "TWSE",
        "endpoint": "BFI82U",
        "unit": "元",
        "display_unit": "億",
        "title": "三大法人買賣金額統計表",
        "updated_at": _now_iso(),
        "foreign": None,
        "trust": None,
        "dealer": None,
        "dealer_proprietary": None,
        "dealer_hedge": None,
        "foreign_dealer": None,
        "total": None,
        "rows": [],
        "note": note,
    }


def candidate_days(prefer: str | None = None, lookback: int = 12) -> list[str]:
    """Prefer given YYYYMMDD / YYYY-MM-DD, else today, then prior calendar days."""
    out: list[str] = []
    if prefer:
        p = prefer.replace("-", "").strip()
        if len(p) == 8 and p.isdigit():
            out.append(p)
    today = _now_taipei().date()
    for i in range(0, lookback):
        d = today - timedelta(days=i)
        key = d.strftime("%Y%m%d")
        if key not in out:
            out.append(key)
    return out


def fetch_latest(prefer: str | None = None, lookback: int = 12) -> dict:
    """Try prefer/today then walk back until BFI82U has data (skip holidays)."""
    errors: list[str] = []
    for day in candidate_days(prefer, lookback=lookback):
        try:
            raw = fetch_bfi82u(day)
        except Exception as exc:  # noqa: BLE001 — surface in note
            errors.append(f"{day}:{type(exc).__name__}")
            continue
        parsed = parse_bfi82u(raw, day)
        if parsed is not None:
            if prefer and day != prefer.replace("-", ""):
                parsed["note"] = (
                    f"指定日無資料，改用最近交易日 {parsed['date']}。"
                    + str(parsed.get("note") or "")
                )
            elif day != _now_taipei().strftime("%Y%m%d"):
                parsed["note"] = (
                    f"今日尚無／非交易日，顯示最近交易日 {parsed['date']}。"
                    + str(parsed.get("note") or "")
                )
            return parsed
        errors.append(f"{day}:empty")
    note = "TWSE 近幾日皆無三大法人資料"
    if errors:
        note += "（" + ",".join(errors[-5:]) + "）"
    return empty_payload(note, candidate_days(prefer, 1)[0])


def save_cache(payload: dict, path: Path | None = None) -> Path:
    path = path or CACHE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        STAMP_PATH.write_text(_now_iso(), encoding="utf-8")
    except OSError:
        pass
    return path


def load_cache(path: Path | None = None) -> dict:
    path = path or CACHE_PATH
    if not path.exists():
        return empty_payload("尚未抓取三大法人")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else empty_payload("快取損壞")
    except (OSError, json.JSONDecodeError):
        return empty_payload("快取讀取失敗")


def _journal_has(date_s: str) -> bool:
    if not JOURNAL_PATH.exists() or JOURNAL_PATH.stat().st_size == 0:
        return False
    try:
        with JOURNAL_PATH.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if str(row.get("date") or "") == date_s:
                    return True
    except OSError:
        return False
    return False


def append_journal(payload: dict) -> Path:
    """Append one row per trade date. Skips duplicate date. Never touches account.json."""
    PAPER.mkdir(parents=True, exist_ok=True)
    date_s = str(payload.get("date") or "")
    if date_s and _journal_has(date_s):
        return JOURNAL_PATH
    foreign = payload.get("foreign") or {}
    trust = payload.get("trust") or {}
    dealer = payload.get("dealer") or {}
    dprop = payload.get("dealer_proprietary") or {}
    dhedge = payload.get("dealer_hedge") or {}
    total = payload.get("total") or {}
    row = {
        "logged_at": payload.get("updated_at") or _now_iso(),
        "date": date_s,
        "foreign_net": foreign.get("net", ""),
        "foreign_net_yi": foreign.get("net_yi", ""),
        "trust_net": trust.get("net", ""),
        "trust_net_yi": trust.get("net_yi", ""),
        "dealer_net": dealer.get("net", ""),
        "dealer_net_yi": dealer.get("net_yi", ""),
        "dealer_prop_net": dprop.get("net", ""),
        "dealer_hedge_net": dhedge.get("net", ""),
        "total_net": total.get("net", ""),
        "total_net_yi": total.get("net_yi", ""),
        "source": payload.get("source") or "TWSE",
        "ok": int(bool(payload.get("ok"))),
        "note": str(payload.get("note") or "")[:200],
    }
    write_header = not JOURNAL_PATH.exists() or JOURNAL_PATH.stat().st_size == 0
    with JOURNAL_PATH.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=JOURNAL_COLS)
        if write_header:
            w.writeheader()
        w.writerow(row)
    return JOURNAL_PATH


def run_fetch(prefer: str | None = None) -> dict:
    payload = fetch_latest(prefer=prefer)
    save_cache(payload)
    if payload.get("ok"):
        append_journal(payload)
    return payload


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(
        description="TWSE 三大法人 BFI82U（不成交、不改帳戶）"
    )
    ap.add_argument(
        "--fetch",
        action="store_true",
        help="抓取並寫入 paper/institutional.json（預設動作）",
    )
    ap.add_argument("--date", default="", help="指定 YYYYMMDD 或 YYYY-MM-DD")
    ap.add_argument(
        "--show",
        action="store_true",
        help="只顯示現有快取，不抓網",
    )
    args = ap.parse_args()

    if args.show:
        payload = load_cache()
    else:
        # --fetch or bare invocation both fetch
        payload = run_fetch(prefer=(args.date or None))

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not payload.get("ok"):
        sys.exit(2)


if __name__ == "__main__":
    main()