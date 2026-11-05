"""自選股排名：輸出每月每檔的預測分數與全市場排名（CSV + JSON，給之後的 RAG 用）。
兩種模式：
  python watchlist.py                 # 歷史：用 out/preds_tf.pkl（每月由當時最新、已訓練的 TF-NN3 做的樣本外預測）
  python watchlist.py --live          # 最新月：從正式來源 out/preds_tf_real.pkl 讀取 TF-NN3（不重新訓練），
                                      # 產出 out/live_preds_all.csv，分數與正式來源一致。
  可加 --codes 3450,6197,...
資料路徑由環境變數 PANEL_PATH 決定，預設 trade_NN/data/panel.pkl（相對於本檔所在資料夾）。
"""
import argparse, json, os, numpy as np, pandas as pd
from nn_tf import FEAT, PANEL_PATH

DEFAULT = "3450,6197,5314,6617,3694,3023,3605,6279,2392,3533"
ap = argparse.ArgumentParser()
ap.add_argument("--codes", default=DEFAULT)
ap.add_argument("--live", action="store_true")
a = ap.parse_args()
codes = a.codes.split(",")

def rank_table(df, col):
    df = df.copy()
    df["rank"] = df.groupby("mon")[col].rank(ascending=False, method="min").astype(int)
    df["n_stocks"] = df.groupby("mon")[col].transform("size")
    df["pct"] = 1 - (df["rank"] - 1) / df["n_stocks"]
    df["decile"] = np.ceil(df["pct"] * 10).clip(1, 10).astype(int)
    return df

if not a.live:
    D = pd.read_pickle("out/preds_tf.pkl")
    D = rank_table(D, "TF-NN3")
    W = D[D.code.isin(codes)][["mon", "code", "TF-NN3", "rank", "n_stocks", "pct", "decile", "ret_next", "y"]]
    W = W.rename(columns={"TF-NN3": "pred_excess_ret", "ret_next": "realized_ret_next", "y": "realized_excess_next"})
    tag = "history"
else:
    # v5：--live 不重新訓練，直接從正式來源 preds_tf_real.pkl 讀取最新月份的 TF-NN3
    R = pd.read_pickle("out/preds_tf_real.pkl")
    R["ym"] = R["mon"].astype(str).str[:7]
    latest = R["ym"].max()
    L = R[R["ym"] == latest].copy()
    L["pred_excess_ret"] = L["TF-NN3"]
    L["mon"] = latest
    L = rank_table(L, "pred_excess_ret")
    A = L[["mon", "code", "pred_excess_ret", "rank", "n_stocks", "pct", "decile"]].copy()
    A.to_csv("out/live_preds_all.csv", index=False, encoding="utf-8-sig")
    W = L[L.code.isin(codes)][["mon", "code", "pred_excess_ret", "rank", "n_stocks", "pct", "decile"]]
    tag = "live"
W["mon"] = W["mon"].astype(str)
W = W.sort_values(["mon", "rank"])
miss = sorted(set(codes) - set(W.code))
print("缺資料的代號:", miss)
W.to_csv(f"out/watchlist_{tag}.csv", index=False, encoding="utf-8-sig")
json.dump({"model": "TF-NN3 (formal preds_tf_real.pkl for live)", "target": "next-month return minus sample VW market return",
  "mode": tag, "missing_codes": miss, "records": W.round(6).to_dict("records")}, open(f"out/watchlist_{tag}.json", "w"), ensure_ascii=False, indent=1)
print(W.tail(len(codes)).to_string(index=False))
