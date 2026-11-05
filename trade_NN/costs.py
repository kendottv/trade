"""交易成本：手續費 0.1425%（買賣）、證交稅 0.3%（賣）、滑價假設 0.1%（買賣各一次）。"""
FEE, TAX, SLIP = 0.001425, 0.003, 0.001
BUY  = FEE + SLIP          # 0.2425%
SELL = FEE + TAX + SLIP    # 0.5425%
def trade_cost(w_old, w_new):
    """w_old: 上期權重（已依報酬漂移）、w_new: 目標權重（dict/Series, 可含負值=放空）。回傳 (成本占淨值比, 單邊週轉率)。
    多頭：增加=買、減少=賣；空頭：加碼放空=賣、回補=買。"""
    import pandas as pd
    o=pd.Series(w_old,dtype=float); n=pd.Series(w_new,dtype=float); idx=o.index.union(n.index)
    d=n.reindex(idx).fillna(0)-o.reindex(idx).fillna(0)
    buy=d.clip(lower=0).sum(); sell=(-d).clip(lower=0).sum()
    return buy*BUY+sell*SELL, d.abs().sum()/2
