"""風控工具：產業對照、beta、波動度、beta 中性。
規格 v4 AC-5：industry.csv 來自 TWSE ISIN 和 TPEx OpenAPI 的現行分類（code,name,market,industry），
不加日期維度。最新月份 panel 查不到產業的一律歸「未知」並受 15% 上限。
回測使用現行產業分類，非當時分類。
"""
import numpy as np, pandas as pd, os
HERE = os.path.dirname(os.path.abspath(__file__))

def industry_map():
    """讀取 data/industry.csv（現行分類：上市＝TWSE ISIN 公開頁、上櫃＝TPEx OpenAPI）。
    查不到或已下市 → 「未知」（受 15% 產業上限）。無日期維度。"""
    path = os.path.join(HERE, "data/industry.csv")
    if not os.path.exists(path):
        return {}
    I = pd.read_csv(path, dtype=str)
    return dict(zip(I.code, I.industry))

def realized_beta(r, m):
    r, m = pd.Series(r), pd.Series(m)
    v = r.notna() & m.notna()
    return np.cov(r[v], m[v])[0, 1] / m[v].var()

def ann_vol(r, ppy=12):
    return pd.Series(r).std() * np.sqrt(ppy) * 100

def beta_neutral(wl, ws, beta):
    """多頭權重 wl（總和 1）、空頭權重 ws（總和 1）；縮放空頭使組合事前 beta=0。beta 缺值以 1 代替。"""
    b = lambda w: (pd.Series(w) * pd.Series(beta).reindex(pd.Series(w).index).fillna(1.0)).sum()
    k = b(wl) / max(b(ws), 1e-6)
    return pd.concat([pd.Series(wl), -k * pd.Series(ws)]).groupby(level=0).sum()
