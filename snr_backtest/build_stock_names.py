r"""建股票代號→公司名稱對照表 trade_NN\data\stock_names.csv。
主來源：永豐 Shioaji 合約（api.Contracts.Stocks TSE/OTC/OES .name，經 quotes.get_feed() 既有登入路徑，simulation）。
備援（只補 Shioaji 沒有的代號，例如已下市）：TWSE ISIN 上市/上櫃/興櫃頁、TPEx OpenAPI、TWSE 終止上市清單。不猜名稱。"""
from __future__ import annotations

import csv
import json
import re
import ssl
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

OUT = Path(r"C:\Users\AUSER\Desktop\trade_NN\data\stock_names.csv")
MKT = {"TSE": "上市", "OTC": "上櫃", "OES": "興櫃"}


def _get(url: str, enc: str = "utf-8") -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=40, context=ctx) as r:
            return r.read().decode(enc, "replace")
    except ssl.SSLError:  # TWSE 憑證鏈偶爾缺中繼憑證
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=40, context=ctx) as r:
            return r.read().decode(enc, "replace")


def from_shioaji() -> dict:
    import quotes
    feed = quotes.get_feed()
    if feed.name != "shioaji":
        raise RuntimeError("永豐沒接上（feed=%s）" % feed.name)
    S = feed.impl.api.Contracts.Stocks
    out = {}
    for ex, mk in MKT.items():
        for c in getattr(S, ex):
            nm = str(getattr(c, "name", "") or "").strip()
            if c.code and nm:
                out[str(c.code)] = (nm, mk, "shioaji")
    return out


def from_public() -> tuple[dict, list[str]]:
    out, log = {}, []
    for mode, mk in ((2, "上市"), (4, "上櫃"), (5, "興櫃")):  # 創新板在 strMode=2 內（市場別「上市臺灣創新板」）
        try:
            h = _get(f"https://isin.twse.com.tw/isin/C_public.jsp?strMode={mode}", "cp950")
            n = 0
            for code, name, mkt in re.findall(r"<td bgcolor=#FAFAD2>([0-9A-Z]{4,6})\u3000([^<]+?)</td>.*?<td bgcolor=#FAFAD2>(上市[^<]*|上櫃[^<]*|興櫃[^<]*)</td>", h, re.S):
                out.setdefault(code, (name.strip(), mkt.strip() or mk, f"twse_isin_{mode}")); n += 1
            log.append(f"ISIN strMode={mode}: {n}")
        except Exception as exc:  # noqa: BLE001
            log.append(f"ISIN strMode={mode} 失敗 {type(exc).__name__}")
    for url, mk in (("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes", "上櫃"),
                    ("https://www.tpex.org.tw/openapi/v1/tpex_esb_latest_statistics", "興櫃")):
        try:
            rows = json.loads(_get(url)); n = 0
            for r in rows:
                code = r.get("SecuritiesCompanyCode") or r.get("Code")
                name = r.get("CompanyName") or r.get("Name")
                if code and name:
                    out.setdefault(code.strip(), (name.strip(), mk, "tpex_openapi")); n += 1
            log.append(f"TPEx {url.rsplit('/', 1)[-1]}: {n}")
        except Exception as exc:  # noqa: BLE001
            log.append(f"TPEx {url.rsplit('/', 1)[-1]} 失敗 {type(exc).__name__}")
    try:  # 終止上市
        j = json.loads(_get("https://www.twse.com.tw/rwd/zh/company/suspendListing?response=json")); n = 0
        for r in j.get("data") or []:
            name, code = str(r[1]).strip(), str(r[2]).strip()
            if re.fullmatch(r"[0-9A-Z]{4,6}", code):
                out.setdefault(code, (name, "終止上市", "twse_delisted")); n += 1
        log.append(f"TWSE 終止上市: {n}")
    except Exception as exc:  # noqa: BLE001
        log.append(f"TWSE 終止上市 失敗 {type(exc).__name__}")
    return out, log


def build() -> dict:
    names = {}
    stat = {}
    try:
        names = from_shioaji()
        stat["shioaji"] = len(names)
    except Exception as exc:  # noqa: BLE001
        stat["shioaji_error"] = f"{type(exc).__name__}: {exc}"
    pub, log = from_public()
    added = 0
    for code, v in pub.items():
        if code not in names and (len(code) == 4 or code.startswith("00")):  # 排除權證等
            names[code] = v; added += 1
    stat["public_fallback_added"] = added
    stat["public_log"] = log
    if not names:
        raise RuntimeError("沒有任何來源成功，保留舊檔")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(["code", "name", "market", "source", "updated"])
        for code in sorted(names):
            nm, mk, src = names[code]; w.writerow([code, nm, mk, src, now])
    tmp.replace(OUT)
    stat["total"] = len(names)
    return stat


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=1))
    sys.stdout.flush()
    import os; os._exit(0)  # 不等 shioaji 背景執行緒