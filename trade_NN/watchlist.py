"""自選股排名：輸出每月每檔的預測分數與全市場排名（CSV + JSON，給之後的 RAG 用）。
兩種模式：
  python watchlist.py                 # 歷史：用 out/preds_tf.pkl（每月由當時最新、已訓練的 TF-NN3 做的樣本外預測）
  python watchlist.py --live          # 最新月：用全部已實現資料重訓 TF-NN3（5 seeds），替最新一個特徵月（尚無下月報酬）打分
  可加 --codes 3450,6197,...
"""
import argparse, json, numpy as np, pandas as pd
DEFAULT="3450,6197,5314,6617,3694,3023,3605,6279,2392,3533"   # 後 5 檔是 6197 連接器同業：信邦、宏致、胡連、正崴、嘉澤
ap=argparse.ArgumentParser(); ap.add_argument("--codes",default=DEFAULT); ap.add_argument("--live",action="store_true"); a=ap.parse_args()
codes=a.codes.split(",")
def rank_table(df,col):
    df=df.copy(); df["rank"]=df.groupby("mon")[col].rank(ascending=False,method="min").astype(int)
    df["n_stocks"]=df.groupby("mon")[col].transform("size"); df["pct"]=1-(df["rank"]-1)/df["n_stocks"]
    df["decile"]=np.ceil(df["pct"]*10).clip(1,10).astype(int)   # 10 = 預測最高的一組
    return df
if not a.live:
    D=pd.read_pickle("out/preds_tf.pkl"); D=rank_table(D,"TF-NN3")
    W=D[D.code.isin(codes)][["mon","code","TF-NN3","rank","n_stocks","pct","decile","ret_next","y"]]
    W=W.rename(columns={"TF-NN3":"pred_excess_ret","ret_next":"realized_ret_next","y":"realized_excess_next"}); tag="history"
else:
    from nn_tf import FEAT, fit_ensemble, SRC
    P=pd.read_pickle(f"{SRC}/data_tej2/panel.pkl"); P=P.dropna(subset=["mcap","mom_12"])
    # 與 load_panel 相同的特徵前處理，但保留最新月（ret_next 尚未實現）
    for c in FEAT:
        s=P[c].replace([np.inf,-np.inf],np.nan); s=s.groupby(P["mon"]).transform(lambda x:x.clip(x.quantile(.01),x.quantile(.99)))
        P[c]=s.groupby(P["mon"]).transform(lambda x:(x-x.mean())/x.std()).fillna(0)
    R=P.dropna(subset=["ret_next"]).copy()
    R["rn"]=R.groupby("mon")["ret_next"].transform(lambda s:s.clip(s.quantile(.025),s.quantile(.975)))
    mk=R.groupby("mon").apply(lambda d:np.average(d["ret_next"],weights=d["mcap"])); R["y"]=R["rn"]-R["mon"].map(mk)
    months=sorted(R["mon"].unique()); nva=60; tr,va=months[:-nva],months[-nva:]
    l1=pd.read_csv("out/tf_hyperparams.csv")["l1"].iloc[-1]          # 沿用最後一次重訓選到的 L1
    f=fit_ensemble(R[R.mon.isin(tr)][FEAT].values.astype("float32"),R[R.mon.isin(tr)]["y"].values.astype("float32"),
                   R[R.mon.isin(va)][FEAT].values.astype("float32"),R[R.mon.isin(va)]["y"].values.astype("float32"),l1)
    L=P[P["mon"]==P["mon"].max()].copy(); L["pred_excess_ret"]=f(L[FEAT].values.astype("float32")); L=rank_table(L,"pred_excess_ret")
    A=L[["mon","code","pred_excess_ret","rank","n_stocks","pct","decile"]].copy(); A["mon"]=A["mon"].dt.strftime("%Y-%m")
    A.to_csv("out/live_preds_all.csv",index=False,encoding="utf-8-sig")   # 全市場最新月預測（paper_trade.py 用）
    W=L[L.code.isin(codes)][["mon","code","pred_excess_ret","rank","n_stocks","pct","decile"]]; tag="live"
W["mon"]=W["mon"].dt.strftime("%Y-%m"); W=W.sort_values(["mon","rank"])
miss=sorted(set(codes)-set(W.code)); print("缺資料的代號:",miss)
W.to_csv(f"out/watchlist_{tag}.csv",index=False,encoding="utf-8-sig")
json.dump({"model":"TF-NN3 (32-16-8, BN, L1, 5-seed ensemble)","target":"next-month return minus sample VW market return",
  "mode":tag,"missing_codes":miss,"records":W.round(6).to_dict("records")},open(f"out/watchlist_{tag}.json","w"),ensure_ascii=False,indent=1)
print(W.tail(len(codes)).to_string(index=False))
