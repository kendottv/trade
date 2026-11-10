"""用法: python filter_20ma.py [20 60 ...]（預設20）
大盤濾網：加權指數(^TWII)收盤 < 20日均線 → 抱現金。比較原擇時策略(TF-NN3 預測>0持有6197，否則市場)。
月版：每月底訊號；日版：用前一日收盤判斷，當日報酬用 6197 日還原報酬 / ^TWII 日報酬(市場代理)。
成本：6197 買0.1425% 賣0.4425%；市場腿進出現金視為0050，買0.1425% 賣0.2425%。"""
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
for f in fm.findSystemFonts():
    if "CJK" in f: fm.fontManager.addfont(f)
plt.rcParams["font.family"]=["Noto Sans CJK TC"]; plt.rcParams["axes.unicode_minus"]=False
B,S6,SE=0.001425,0.004425,0.002425
m=pd.read_csv("out/6197_monthly.csv",index_col=0,parse_dates=True)  # 列 t = 月底t訊號，報酬為 t+1 月
r,mk,pred=m["6197報酬"].fillna(0),m["市場"],m["TF-NN3"]
tw=pd.read_pickle("/workspace/alphago_tw_replication/data/twii_daily.pkl")["Close"]["^TWII"].dropna()
px=pd.read_pickle("/workspace/alphago_tw_replication/data/px_daily.pkl")[("6197.TW","Adj Close")].dropna()
import sys
WS=[int(x) for x in sys.argv[1:]] or [20]; TAG=WS[-1]
BEL={w:(tw<tw.rolling(w).mean()) for w in WS}
def costs(state):  # state: 'S'(6197) 'M'(市場) 'C'(現金)，回傳每期扣除成本
    prev=state.shift(fill_value="C"); c=np.zeros(len(state))
    for i,(a,b) in enumerate(zip(prev,state)):
        if a!=b:
            c[i]+= {"S":S6,"M":SE,"C":0}[a]+{"S":B,"M":B,"C":0}[b]
    c[-1]+={"S":S6,"M":SE,"C":0}[state.iloc[-1]]; return c
def ntr(state):
    prev=state.shift(fill_value="C"); return int(((prev!=state)&(prev!="C")).sum()+((prev!=state)&(state!="C")).sum()+(state.iloc[-1]!="C"))
def st(s,ppy,cash=None):
    c=(1+s).cumprod(); n=len(s)/ppy
    d={"CAGR%":(c.iloc[-1]**(1/n)-1)*100,"累積報酬%":(c.iloc[-1]-1)*100,"Sharpe":s.mean()/s.std()*np.sqrt(ppy),"最大回撤%":((c/c.cummax())-1).min()*100}
    d["現金比例%"]=np.nan if cash is None else cash*100; return d
rows=[];curves={}
# ---- 月版 ----
base=pd.Series(np.where(pred>0,"S","M"),m.index)
for name,stt in [("原策略(月)",base)]+[(f"原策略+{w}MA濾網(月)",base.where(~BEL[w].reindex(m.index,method="ffill"),"C")) for w in WS]:
    g=pd.Series(np.select([stt=="S",stt=="M"],[r,mk],0.0),m.index); n=g-costs(stt)
    curves[name]=n; rows.append({"策略":name,**st(n,12,(stt=="C").mean()),"交易次數(單邊)":ntr(stt)})
bh=r.copy(); bh.iloc[0]-=B; bh.iloc[-1]-=S6; curves["買進持有6197"]=bh; rows.append({"策略":"買進持有6197",**st(bh,12,0),"交易次數(單邊)":2})
curves["市場(樣本市值加權)"]=mk; rows.append({"策略":"市場(樣本市值加權)",**st(mk,12,0),"交易次數(單邊)":0})
# ---- 日版 ----
start=m.index[0]+pd.Timedelta(days=1); end=m.index[-1]+pd.offsets.MonthEnd(1)
days=tw.index[(tw.index>=start)&(tw.index<=end)]
dr6=px.pct_change().reindex(days).fillna(0); drm=tw.pct_change().reindex(days)
mon=pd.Series(base.values,index=m.index+pd.offsets.MonthEnd(1))  # 適用月份
bd=pd.Series([mon.get(d+pd.offsets.MonthEnd(0),"M") for d in days],days)
dcurves={}
for name,stt in [("原策略(日, 市場=^TWII)",bd)]+[(f"原策略+{w}MA濾網(日)",bd.where(~BEL[w].shift(1).reindex(days).fillna(False).astype(bool),"C")) for w in WS]:
    g=pd.Series(np.select([stt=="S",stt=="M"],[dr6,drm],0.0),days); n=g-costs(stt)
    dcurves[name]=n; rows.append({"策略":name,**st(n,252,(stt=="C").mean()),"交易次數(單邊)":ntr(stt)})
T=pd.DataFrame(rows).round(2); T.to_csv(f"out/filter_{TAG}ma_metrics.csv",index=False,encoding="utf-8-sig"); print(T.to_string())
ax=plt.figure(figsize=(12,6)).gca()
for k,v in curves.items(): ax.plot(v.index+pd.offsets.MonthEnd(1),(1+v).cumprod(),label=k,lw=2.5 if "濾網" in k else 1.5)
for k,v in dcurves.items(): ax.plot(v.index,(1+v).cumprod(),ls="--",label=k)
ax.set_yscale("log"); ax.legend(); ax.set_title(f"佳必琪(6197) 擇時策略 + 加權指數{"/".join(map(str,WS))}日均線濾網（扣成本，對數軸）")
plt.tight_layout(); plt.savefig(("out/cumret_6197_filter.png" if WS==[20] else f"out/cumret_6197_filter{TAG}.png"),dpi=150)
