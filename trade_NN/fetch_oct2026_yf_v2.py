# 用 yfinance 補 2026/10 月資料（TEJ 匯出只到 2026/09）。股數沿用 2026/09 TEJ 市值/收盤。
# 規格 v4 AC-8：已移除「if 0:」誤導結構，迴圈不再在條件關閉時仍執行。
# AC-10：yfinance 僅暫補，標「暫定」，可重算。正式來源 TEJ。
import yfinance as yf, pandas as pd, numpy as np, time, os

P = pd.read_pickle("data/panel.pkl")
S = P[P.mon == "2026-09-30"][["code", "close", "mcap"]].copy()
S["sh"] = S["mcap"] / S["close"]
codes = S.code.tolist()

def dl(tk):
    d = yf.download(tk, start="2026-09-20", end="2026-11-01", auto_adjust=False, progress=False, threads=True, group_by="ticker")
    return d

rows = {}
if os.path.exists("data/oct2026_yf.csv"):
    for r in pd.read_csv("data/oct2026_yf.csv", dtype={"code": str}).to_dict("records"):
        rows[r["code"]] = {k: r[k] for k in ["code", "close", "vol", "ret", "last", "sep_close_yf"]}

for rnd in range(3):
    for suf in [".TW", ".TWO"]:
        todo = [c for c in codes if c not in rows]
        for i in range(0, len(todo), 50):
            time.sleep(20)
            d = dl([c + suf for c in todo[i:i + 50]])
            for c in todo[i:i + 50]:
                try:
                    x = d[c + suf].dropna(subset=["Close"])
                except KeyError:
                    continue
                o = x[(x.index >= "2026-10-01") & (x.index <= "2026-10-31")]
                s = x[x.index <= "2026-09-30"]
                if len(o) < 5 or len(s) == 0:
                    continue
                rows[c] = dict(
                    code=c, close=o.Close.iloc[-1], vol=o.Volume.sum(),
                    ret=o["Adj Close"].iloc[-1] / s["Adj Close"].iloc[-1] - 1,
                    last=o.index[-1].strftime("%Y-%m-%d"),
                    sep_close_yf=s.Close.iloc[-1],
                    source="yfinance_暫定"
                )
    print(rnd, len(rows), flush=True)

R = pd.DataFrame(rows.values()).merge(S, on="code", suffixes=("", "_tej"))
R["volm"] = R["vol"] / 1e6
R["mcap_new"] = R["sh"] * R["close"]
R["turn_raw"] = R["vol"] / R["sh"]
R.to_csv("data/oct2026_yf.csv", index=False)
print(len(codes), len(R))
print(R[["close_tej", "sep_close_yf"]].corr())
print((abs(R.sep_close_yf / R.close_tej - 1) > 0.02).sum(), "檔 9 月收盤 yf/TEJ 差 >2%（暫定，待 TEJ 重算）")
