"""評估：全市場（OOS R²、十分組多空 Sharpe）＋ 佳必琪 6197 擇時策略，TF-NN3 與既有 8 個 sklearn 模型比較。"""
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
for f in fm.findSystemFonts():
    if "CJK" in f: fm.fontManager.addfont(f)
plt.rcParams["font.family"]=["Noto Sans CJK TC"]; plt.rcParams["axes.unicode_minus"]=False
CODE,NAME="6197","佳必琪"; BUY,SELL=0.001425,0.001425+0.003
sk=pd.read_pickle("/workspace/alphago_tw_replication/out/preds.pkl"); tf_=pd.read_pickle("out/preds_tf.pkl")
D=sk.merge(tf_[["mon","code","TF-NN3"]],on=["mon","code"],how="inner")
assert len(D)==len(sk)==len(tf_), (len(D),len(sk),len(tf_))
M=["OLS-3","OLS","ENet","RF","GBRT+H","NN1","NN2","NN3","TF-NN3"]
mk=D.groupby("mon").apply(lambda d:np.average(d["ret_next"],weights=d["mcap"]))
sh=lambda s:s.mean()/s.std()*np.sqrt(12)
# ---- 全市場 ----
rows=[]
for m in M:
    dec=D.groupby("mon")[m].transform(lambda s:pd.qcut(s.rank(method="first"),10,labels=False))
    g=D.assign(dec=dec).groupby(["mon","dec"])
    ew=g["ret_next"].mean().unstack(); vw=g.apply(lambda d:np.average(d["ret_next"],weights=d["mcap"])).unstack()
    rows.append({"模型":m,"樣本外R2%":(1-((D.y-D[m])**2).sum()/(D.y**2).sum())*100,"多空EW_Sharpe":sh(ew[9]-ew[0]),"多空VW_Sharpe":sh(vw[9]-vw[0]),"做多D10_EW_Sharpe":sh(ew[9])})
A=pd.DataFrame(rows); A.loc[len(A)]={"模型":"市場","多空EW_Sharpe":np.nan,"做多D10_EW_Sharpe":sh(mk)}
A.round(3).to_csv("out/all_stocks_metrics.csv",index=False,encoding="utf-8-sig"); print(A.round(3).to_string())
# ---- 6197 ----
S=D[D.code==CODE].set_index("mon").sort_index(); allm=mk.index[(mk.index>=S.index.min())&(mk.index<=S.index.max())]
r=S["ret_next"].reindex(allm); mkt=mk.reindex(allm); ex=r-mkt
def st(s):
    c=(1+s).cumprod(); return {"年化報酬%":s.mean()*1200,"Sharpe":sh(s),"最大回撤%":((c/c.cummax())-1).min()*100,"累積報酬%":(c.iloc[-1]-1)*100,"勝過市場月%":(s>mkt).mean()*100}
def strat(hold):
    hold=hold.reindex(allm).fillna(False).astype(bool); prev=hold.shift(fill_value=False)
    s=pd.Series(np.where(hold,r.fillna(0),mkt),allm)
    sn=s-np.where(hold&~prev,BUY,0)-np.where(~hold&prev,SELL,0); sn.iloc[-1]-=SELL*hold.iloc[-1]
    return s,sn,int((hold!=prev).sum()+hold.iloc[-1]),int(hold.sum())
rows=[];curves={}
for m in M:
    p=S[m].reindex(allm); v=p.notna()&ex.notna(); s,sn,nt,nh=strat(p>0); curves[m]=s
    rows.append({"模型":m,"方向命中率%":(np.sign(p[v])==np.sign(ex[v])).mean()*100,"持有月數":nh,"交易次數":nt,**st(s),**{"扣成本_"+k:v for k,v in st(sn).items()}})
bh=r.fillna(0); bhn=bh.copy(); bhn.iloc[0]-=BUY; bhn.iloc[-1]-=SELL
rows.append({"模型":"買進持有6197","持有月數":len(allm),"交易次數":2,**st(bh),**{"扣成本_"+k:v for k,v in st(bhn).items()}})
rows.append({"模型":"市場(樣本市值加權)",**st(mkt)})
T=pd.DataFrame(rows); T.round(2).to_csv("out/6197_metrics.csv",index=False,encoding="utf-8-sig"); print(T.round(2).to_string())
pd.DataFrame({"實際超額":ex,"6197報酬":r,"市場":mkt,**{m:S[m].reindex(allm) for m in M}}).to_csv("out/6197_monthly.csv",encoding="utf-8-sig")
best=T.iloc[:len(M)].sort_values("Sharpe").iloc[-1]["模型"]
fig,ax=plt.subplots(figsize=(11,5.5))
for m in dict.fromkeys(["TF-NN3",best,"NN3"]): ax.plot(allm,(1+curves[m]).cumprod(),label=f"擇時策略 {m}（預測>0持有，否則市場）")
ax.plot(allm,(1+bh).cumprod(),"k",lw=2.5,label="買進持有 6197"); ax.plot(allm,(1+mkt).cumprod(),color="gray",lw=2.5,label="市場")
ax.set_yscale("log"); ax.grid(alpha=.3); ax.legend(fontsize=8); ax.set_title(f"{NAME}({CODE}) 擇時策略累積報酬（未扣成本，對數座標，2014/04–2026/09）")
plt.tight_layout(); plt.savefig("out/cumret_6197.png",dpi=150); plt.close()
h=T.iloc[:len(M)].set_index("模型")["方向命中率%"]; ax=h.plot.bar(figsize=(10,4.5),rot=0,color=["tab:red" if i=="TF-NN3" else "tab:blue" for i in h.index])
ax.axhline(50,c="k",ls="--"); ax.set_ylabel("方向命中率 (%)"); ax.set_title(f"{NAME}({CODE}) 預測方向命中率：TF-NN3（紅）vs sklearn 模型"); plt.tight_layout(); plt.savefig("out/hitrate_6197.png",dpi=150); plt.close()
fig,axs=plt.subplots(1,2,figsize=(14,5))
axs[0].plot(allm,ex*100,"k",lw=1,label="實際超額報酬"); axs[0].plot(allm,S["TF-NN3"].reindex(allm)*100*10,"r",label="TF-NN3 預測 ×10（放大方便看）"); axs[0].axhline(0,c="gray"); axs[0].legend(); axs[0].set_ylabel("%"); axs[0].set_title("每月預測 vs 實際（時間序列）")
axs[1].scatter(S["TF-NN3"].reindex(allm)*100,ex*100,s=12); axs[1].axhline(0,c="k",lw=.8); axs[1].axvline(0,c="k",lw=.8); axs[1].set_xlabel("TF-NN3 預測超額 (%)"); axs[1].set_ylabel("實際超額 (%)"); axs[1].set_title("散佈圖")
plt.tight_layout(); plt.savefig("out/pred_vs_actual_6197.png",dpi=150)
print("best",best)
