"""【LEGACY】投組回測（非 real 口徑）。
正式回測請改用 backtest_real.py（下市 −100%、開盤成交、無 fillna(0) 路徑）。
規格 v4 AC-2 / AC-3。
資料路徑由環境變數 PANEL_PATH 決定，預設 trade_NN/data/panel.pkl（相對於本檔所在資料夾）。
輸出：out/portfolio_metrics.csv、portfolio_monthly.csv、portfolio_subperiods.csv、ic_monthly.csv、cumret_portfolio.png
"""
import os, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
for f in fm.findSystemFonts():
    if "CJK" in f:
        fm.fontManager.addfont(f)
plt.rcParams["font.family"] = ["Noto Sans CJK TC"]
plt.rcParams["axes.unicode_minus"] = False
from portfolio import liquidity_screen, select, weights
from risk import industry_map, realized_beta, ann_vol, beta_neutral
from costs import trade_cost

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PANEL = os.path.join(HERE, "data", "panel.pkl")
PANEL_PATH = os.environ.get("PANEL_PATH", DEFAULT_PANEL)


def load():
    D = pd.read_pickle("out/preds_tf.pkl").rename(columns={"TF-NN3": "score"})
    P = pd.read_pickle(PANEL_PATH)[["mon", "code", "dv", "beta", "ret_next"]]
    D = D.merge(P, on=["mon", "code"], how="left")
    # AC-1 計數（測試月份 ret_next 缺值）
    missing = D["ret_next"].isna().sum()
    print(f"AC-1：測試月份 ret_next 缺值股票計數 = {missing}")
    D["ret_next"] = D["ret_next"].fillna(0)  # legacy 路徑，正式版已移除
    mk = D.groupby("mon").apply(lambda d: np.average(d["ret_next"], weights=d["mcap"]))
    return D, mk


VAR = {
    "Top20 等權 無緩衝": (20, "ew", None, None, False),
    "Top20 等權 緩衝40": (20, "ew", 40, None, False),
    "Top20 分數加權 緩衝40": (20, "score", 40, None, False),
    "Top20 等權 緩衝40 產業≤30%": (20, "ew", 40, 0.3, False),
    "十分位 等權 無緩衝": ("dec", "ew", None, None, False),
    "十分位 等權 緩衝(前20%續抱)": ("dec", "ew", "dec2", None, False),
    "多空 D10−D1 beta中性": ("dec", "ew", None, None, True)
}


def run(D, mk, ind):
    out = {}
    gross = {}
    turn = {}
    beta_ex = {}
    months = sorted(D.mon.unique())
    for name, (n, sch, buf, icap, ls) in VAR.items():
        prev = pd.Series(dtype=float)
        R = []
        G = []
        T = []
        B = []
        for m in months:
            u = liquidity_screen(D[D.mon == m])
            N = len(u) // 10 if n == "dec" else n
            K = {None: None, "dec2": 2 * N}.get(buf, buf)
            longs, _, _ = select(u, N, prev=list(prev[prev > 0].index), buffer=K, ind=ind, ind_cap=icap)
            w = weights(u, longs, sch)
            if ls:
                shorts = list(u.sort_values("score").code[:N])
                w = beta_neutral(w, weights(u, shorts, "ew"), u.set_index("code")["beta"])
            c, t = trade_cost(prev, w)
            r = u.set_index("code")["ret_next"]
            rr = r.reindex(w.index).fillna(0)
            g = (w * rr).sum()
            R.append(g - c)
            G.append(g)
            T.append(t)
            B.append((w * u.set_index("code")["beta"].reindex(w.index).fillna(1)).sum())
            prev = w * (1 + rr) / (1 + g) if not ls else w * (1 + rr) / (1 + g)
        idx = pd.DatetimeIndex(months)
        out[name] = pd.Series(R, idx)
        gross[name] = pd.Series(G, idx)
        turn[name] = pd.Series(T, idx)
        beta_ex[name] = np.mean(B)
    return out, gross, turn, beta_ex


def stats(s, m, ppy=12):
    c = (1 + s).cumprod()
    y = len(s) / ppy
    return {"CAGR%": (c.iloc[-1] ** (1 / y) - 1) * 100, "累積報酬%": (c.iloc[-1] - 1) * 100,
            "Sharpe": s.mean() / s.std() * np.sqrt(ppy),
            "最大回撤%": ((c / c.cummax()) - 1).min() * 100, "年化波動%": ann_vol(s),
            "實現beta": realized_beta(s, m), "勝過市場月%": (s > m).mean() * 100}


def ic_series(D):
    return D.groupby("mon").apply(lambda d: d["score"].corr(d["ret_next"], method="spearman"))


if __name__ == "__main__":
    D, mk = load()
    ind = industry_map()
    out, gross, turn, bex = run(D, mk, ind)
    mk = mk.reindex(out[next(iter(out))].index)
    rows = []
    for k in out:
        rows.append({"策略": k, **stats(out[k], mk), "毛CAGR%": stats(gross[k], mk)["CAGR%"],
                     "月均單邊週轉%": turn[k].mean() * 100, "事前beta": bex[k]})
    rows.append({"策略": "市場(樣本市值加權)", **stats(mk, mk), "月均單邊週轉%": 0})
    T = pd.DataFrame(rows).round(2)
    T.to_csv("out/portfolio_metrics.csv", index=False, encoding="utf-8-sig")
    ic = ic_series(D)
    ics = pd.DataFrame({"IC_all": ic, "IC_liquid": D.groupby("mon").apply(
        lambda d: (lambda u: u["score"].corr(u["ret_next"], method="spearman"))(liquidity_screen(d)))})
    ics.to_csv("out/ic_monthly.csv", encoding="utf-8-sig")
    M = pd.DataFrame(out)
    M["市場"] = mk
    M.to_csv("out/portfolio_monthly.csv", encoding="utf-8-sig")
    per = [("2014–2017", "2014", "2017"), ("2018–2021", "2018", "2021"), ("2022–2026/08", "2022", "2026")]
    sp = []
    for lab, a, b in per:
        for k in ["Top20 等權 緩衝40", "十分位 等權 無緩衝", "多空 D10−D1 beta中性", "市場"]:
            s = M[k].loc[a:b]
            st = stats(s, M["市場"].loc[a:b])
            sp.append({"期間": lab, "策略": k, "CAGR%": st["CAGR%"], "Sharpe": st["Sharpe"],
                       "最大回撤%": st["最大回撤%"], "IC均值": ics["IC_all"].loc[a:b].mean()})
    SP = pd.DataFrame(sp).round(3)
    SP.to_csv("out/portfolio_subperiods.csv", index=False, encoding="utf-8-sig")
    for c in ics:
        print(f"{c}: mean={ics[c].mean():.4f} t={ics[c].mean()/ics[c].std()*np.sqrt(ics[c].count()):.2f} 正IC月%={(ics[c]>0).mean()*100:.1f}")
    print(T.to_string())
    print(SP.to_string())
    ax = plt.figure(figsize=(12, 6)).gca()
    for k in M:
        ax.plot(M.index + pd.offsets.MonthEnd(1), (1 + M[k]).cumprod(), label=k, lw=2.5 if k == "市場" else 1.4,
                color="k" if k == "市場" else None)
    ax.set_yscale("log")
    ax.legend(fontsize=9)
    ax.set_title("TF-NN3 投組回測（樣本外，扣手續費/稅/滑價，對數軸）【LEGACY】")
    plt.tight_layout()
    plt.savefig("out/cumret_portfolio.png", dpi=150)
