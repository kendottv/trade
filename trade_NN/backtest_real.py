"""現實版回測（主策略凍結：Top20 等權、緩衝40、產業未知15%/其他30%、單檔≤10%、流動性後20%剔除）。
規格 v4：
- AC-1：測試月份包含 ret_next 缺值股票（計數>0）
- AC-2：下市持股預設 −100%，無 fillna(0) 路徑
- AC-4 / AC-5：select 使用未知 15%、其他 30%；產業為現行分類，查不到歸「未知」
與 backtest_portfolio.py（legacy）的差異見 REAL_RULES.md。
"""
import sys, numpy as np, pandas as pd, os
from portfolio import liquidity_screen, select
from risk import industry_map

FEE, TAX, SLIP, MINFEE = 0.001425, 0.003, 0.001, 20
DELIST = float(sys.argv[1]) if len(sys.argv) > 1 else -1.0
TAG = "" if DELIST == -1.0 else f"_delist{int(DELIST*100)}"


def daily():
    a = pd.read_pickle("data/px_daily.pkl") if os.path.exists("data/px_daily.pkl") else pd.DataFrame()
    b = pd.read_pickle("data/real/px_daily_extra.pkl") if os.path.exists("data/real/px_daily_extra.pkl") else a
    D = {}
    for df in (a, b):
        if df.empty:
            continue
        for t in sorted({c[0] for c in df.columns}):
            code = t.split(".")[0]
            if code in D:
                continue
            x = df[t][["Open", "High", "Close", "Adj Close"]].dropna(subset=["Open", "Close"])
            x = x[(x.Open > 0) & (x.Close > 0)]
            if len(x):
                D[code if t != "0050.TW" else "0050"] = x
    try:
        z = pd.read_pickle("data/real/px_0050.pkl")[["Open", "High", "Close", "Adj Close"]]
        D["0050"] = z[(z.Open > 0) & (z.Close > 0)]
    except Exception:
        pass
    return D


DLY = daily()
P = pd.read_pickle("data/panel.pkl")
last_mon = P.groupby("code").mon.max()
days = pd.DatetimeIndex(sorted(set().union(*[set(v.index) for k, v in DLY.items() if k in ("2330", "0050")]))) if DLY else pd.DatetimeIndex([])
first_day = {p: days[days.to_period("M") == p][0] for p in days.to_period("M").unique()} if len(days) else {}
try:
    TRI = pd.read_csv("data/real/taiex_tri_daily.csv", parse_dates=["date"]).set_index("date")["tri"]
    tri_m = TRI.groupby(TRI.index.to_period("M")).last()
except Exception:
    tri_m = pd.Series(dtype=float)


def limit(d):
    return .07 if d < pd.Timestamp("2015-06-01") else .10


def bar(code, d):
    x = DLY.get(code)
    if x is None or d not in x.index:
        return None
    i = x.index.get_loc(d)
    prev = x.Close.iloc[i - 1] if i > 0 else np.nan
    r = x.loc[d]
    f = r["Adj Close"] / r["Close"]
    return dict(open=r.Open, close=r.Close, high=r.High, adjopen=r.Open * f, adjclose=r["Adj Close"], prev=prev)


def hold_ret(code, m):
    """訊號月 m：t+1 首日開盤 → t+2 首日開盤。下市 −100%，停牌 0。無 fillna(0)。"""
    p = m.to_period("M")
    d0, d1 = first_day.get(p + 1), first_day.get(p + 2)
    a = bar(code, d0) if d0 is not None else None
    if a is not None:
        b = bar(code, d1) if d1 is not None else None
        if b is not None:
            return b["adjopen"] / a["adjopen"] - 1, "daily_open"
        x = DLY.get(code)
        if x is not None:
            x = x[(x.index >= d0) & ((x.index < d1) if d1 is not None else True)]
            if d1 is not None and len(x):
                return x["Adj Close"].iloc[-1] / a["adjopen"] - 1, "daily_lastclose"
    r = Pm.get((m, code), np.nan)
    if pd.notna(r):
        return r, "monthly"
    return (0.0, "suspended") if last_mon.get(code, m) > m + pd.offsets.MonthEnd(1) else (DELIST, "delisted")


Pm = P.set_index(["mon", "code"])["ret_next"].to_dict()
Pc = P.set_index(["mon", "code"])["close"].to_dict()


def run(D, ind, nav0=1_000_000):
    months = sorted(D.mon.unique())
    val = {}
    nav = nav0
    rows = []
    src = {}
    for m in months:
        p = m.to_period("M")
        d0 = first_day.get(p + 1)
        if d0 is None or first_day.get(p + 2) is None:
            break
        u = liquidity_screen(D[D.mon == m].dropna(subset=["dv", "mcap"]))
        prevc = [c for c, v in val.items() if v > 0]
        longs = select(u, 20, prev=prevc, buffer=40, ind=ind, ind_cap=0.30, ind_cap_unknown=0.15)
        info = {c: bar(c, d0) for c in set(longs) | set(val)}
        px = {c: (info[c]["open"] if info[c] else Pc.get((m, c), np.nan)) for c in info}
        tgt = nav / max(len(longs), 1)
        cost = 0
        traded = 0
        new = {}
        blocked = 0
        for c in set(longs) | set(val):
            old = val.get(c, 0.0)
            want = tgt if c in longs else 0.0
            b = info[c]
            lim = limit(d0)
            up = b is not None and b["prev"] > 0 and b["open"] >= b["prev"] * (1 + lim) * 0.995
            dn = b is not None and b["prev"] > 0 and b["open"] <= b["prev"] * (1 - lim) * 1.005
            pr = px[c]
            if want > old:
                if up:
                    new[c] = old
                    blocked += 1
                    continue
                sh = np.floor(want / pr) if pr == pr and pr > 0 else 0
                tv = sh * pr
                buy = max(tv - old, 0)
                new[c] = old + buy
                if buy > 0:
                    cost += max(buy * FEE, MINFEE) + buy * SLIP
                    traded += buy
            elif want < old:
                sh = np.floor(want / pr) if (want > 0 and pr == pr and pr > 0) else 0
                keep = min(sh * pr, old) if want > 0 else 0
                sell = old - keep
                adj = 1.0
                if dn:
                    adj = b["close"] / b["open"]
                cost += max(sell * adj * FEE, MINFEE) + sell * adj * (TAX + SLIP)
                traded += sell
                new[c] = keep
                nav += sell * (adj - 1)
            else:
                new[c] = old
        nav -= cost
        cash = nav - sum(new.values())
        R = {}
        for c, v in new.items():
            if v <= 0:
                continue
            r, s = hold_ret(c, m)
            R[c] = r
            src[s] = src.get(s, 0) + 1
        val = {c: v * (1 + R[c]) for c, v in new.items() if v > 0}
        nav_end = cash + sum(val.values())
        rows.append(dict(mon=m, nav_start=nav + cost, nav_end=nav_end, cost=cost,
                         turn=traded / (nav + cost) / 2, n=len(val), blocked=blocked, cash=cash))
        nav = nav_end
    R = pd.DataFrame(rows).set_index("mon")
    R["ret"] = R.nav_end / R.nav_start - 1
    return R, src


def bench(months):
    o = {}
    for m in months:
        p = m.to_period("M")
        try:
            a, b = bar("0050", first_day[p + 1]), bar("0050", first_day[p + 2])
            o[m] = dict(TAIEX報酬指數=tri_m.get(p + 1, np.nan) / tri_m.get(p, np.nan) - 1 if len(tri_m) else np.nan,
                        **{"0050開盤": b["adjopen"] / a["adjopen"] - 1 if a and b else np.nan})
        except Exception:
            o[m] = dict(TAIEX報酬指數=np.nan, **{"0050開盤": np.nan})
    return pd.DataFrame(o).T


def stats(s, m):
    c = (1 + s).cumprod()
    y = len(s) / 12
    return {"月數": len(s), "CAGR%": (c.iloc[-1] ** (1 / y) - 1) * 100 if y > 0 else np.nan,
            "Sharpe": s.mean() / s.std() * np.sqrt(12) if s.std() > 0 else np.nan,
            "最大回撤%": ((c / c.cummax()) - 1).min() * 100,
            "年化超額(對基準)%": ((c.iloc[-1] ** (1 / y)) - ((1 + m).cumprod().iloc[-1] ** (1 / y))) * 100 if y > 0 else np.nan,
            "勝過基準月%": (s > m).mean() * 100}


PER = [("全期", "2014-03", "2026-08"), ("設計期", "2014-03", "2023-12"), ("保留期", "2024-01", "2026-08")]

if __name__ == "__main__":
    ind = industry_map()
    D = pd.read_pickle(os.environ.get("PREDS", "out/preds_tf_real.pkl")).rename(columns={"TF-NN3": "score"}).merge(
        P[["mon", "code", "dv"]], on=["mon", "code"], how="left")
    R, src = run(D, ind)
    B = bench(R.index)
    R = R.join(B)
    R.to_csv(f"out/portfolio_monthly_real{TAG}.csv", encoding="utf-8-sig")
    print("報酬來源（持股-月）:", src)
    rows = []
    for lab, a, b in PER:
        s = R.loc[a:b]
        rows.append({"期間": lab, "策略": "Top20 現實版", **stats(s.ret, s["TAIEX報酬指數"]),
                     "月均單邊週轉%": s.turn.mean() * 100, "買不到(漲停)次數": int(s.blocked.sum())})
        for k in ["TAIEX報酬指數", "0050開盤"]:
            rows.append({"期間": lab, "策略": k, **stats(s[k], s["TAIEX報酬指數"])})
    T = pd.DataFrame(rows).round(2)
    T.to_csv(f"out/portfolio_metrics_real{TAG}.csv", index=False, encoding="utf-8-sig")
    print(T.to_string())
    print("期末 NAV:", round(R.nav_end.iloc[-1]), "最後持有月:", R.index[-1].date())
