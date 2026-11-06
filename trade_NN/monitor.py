"""模型監控：滾動 12 個月 IC、勝過市場比例，以及紙上交易 vs 回測報酬；偵測衰退。
用法：python monitor.py   （先跑 backtest_portfolio.py；紙上 ledger 有結算月份時會一併比較）
警示規則：滾動12月 IC 連續 6 個月 <0；滾動12月勝率連續 6 個月 <50%；紙上近 6 期平均超額報酬 < 回測月均超額 − 2 個標準誤。"""
import os, sqlite3, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
for f in fm.findSystemFonts():
    if "CJK" in f: fm.fontManager.addfont(f)
plt.rcParams["font.family"]=["Noto Sans CJK TC"]; plt.rcParams["axes.unicode_minus"]=False
MAIN="Top20 等權 緩衝40 產業≤30%"
ic=pd.read_csv("out/ic_monthly.csv",index_col=0,parse_dates=True)["IC_all"]
M=pd.read_csv("out/portfolio_monthly.csv",index_col=0,parse_dates=True); ex=M[MAIN]-M["市場"]
R=pd.DataFrame({"IC":ic,"IC_roll12":ic.rolling(12).mean(),"hit_roll12":(ex>0).rolling(12).mean()*100,"excess":ex,"excess_roll12":ex.rolling(12).mean()*100})
streak=lambda b:b.groupby((~b).cumsum()).cumsum()
R["IC_neg_streak"]=streak(R.IC_roll12<0); R["hit_low_streak"]=streak(R.hit_roll12<50)
R.to_csv("out/monitor.csv",encoding="utf-8-sig"); last=R.iloc[-1]; flags=[]
if last.IC_neg_streak>=6: flags.append(f"滾動12月 IC 已連續 {int(last.IC_neg_streak)} 個月 <0")
if last.hit_low_streak>=6: flags.append(f"滾動12月勝率已連續 {int(last.hit_low_streak)} 個月 <50%")
hist=R[R.IC_neg_streak>=6].index; print(f"回測期間曾觸發 IC 衰退警示的月份數：{len(hist)}" + (f"（{hist.min():%Y-%m}…{hist.max():%Y-%m}）" if len(hist) else ""))
db="paper/paper_ledger.db"; K=pd.DataFrame()
if os.path.exists(db):
    K=pd.read_sql("select * from marks where status='marked' order by mon",sqlite3.connect(db))
if len(K):
    le=K.port_ret-K.mkt_ret; mu,se=ex.mean(),ex.std()/np.sqrt(min(len(le),6))
    print(f"紙上交易 {len(K)} 期：平均超額 {le.mean():.2%}/月 vs 回測 {mu:.2%}/月")
    if len(le)>=3 and le.tail(6).mean()<mu-2*se: flags.append("紙上交易超額報酬明顯低於回測")
else: print("紙上交易尚無已結算月份（需等下個月報酬進資料）")
print(f"最新 {R.index[-1]:%Y-%m}：IC={last.IC:.3f}，滾動12月 IC={last.IC_roll12:.3f}，滾動12月勝率={last.hit_roll12:.0f}%，滾動12月月均超額={last.excess_roll12:.2f}%")
print("⚠ 警示：" + "；".join(flags) if flags else "狀態正常，無衰退警示")
fig,ax=plt.subplots(2,1,figsize=(12,7),sharex=True)
ax[0].bar(R.index,R.IC,width=20,color="lightgray",label="月 IC"); ax[0].plot(R.index,R.IC_roll12,"r",label="滾動12月 IC"); ax[0].axhline(0,c="k"); ax[0].legend()
ax[1].plot(R.index,R.hit_roll12,label="滾動12月勝過市場 %"); ax[1].axhline(50,c="k",ls="--"); ax[1].legend(); ax[0].set_title(f"模型監控（主策略：{MAIN}）")
plt.tight_layout(); plt.savefig("out/monitor.png",dpi=130)
