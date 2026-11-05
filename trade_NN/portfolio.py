"""投組建構：流動性篩選、Top-N / 十分位選股、等權 / 分數加權、單一個股上限、產業上限、持有緩衝區。
規格 v4 AC-4 / AC-6：未知產業上限 15%，其他 30%。
filtered_rank 為流動性篩選後、產業上限前的同一套名次（緩衝 40 與 Top20 共用）。
緩衝與 Top20 邊界包含第 40 名與第 20 名（rank <= 40 保留、rank <= 20 視為合格新買）。
「未知」是一個產業桶，受 15% 上限，不是直接剔除。
"""
import numpy as np, pandas as pd

def liquidity_screen(df, q=0.2):
    """剔除當月成交值(dv)或市值(mcap)落在後 20% 的股票（只用 t 月底已知資料）。
    使用 >= quantile，避免全相同值時全部被嚴格 > 刪除。"""
    if len(df) == 0:
        return df
    return df[(df.dv >= df.dv.quantile(q)) & (df.mcap >= df.mcap.quantile(q))].copy()

def cap_weights(w, cap=0.10, it=50):
    w = pd.Series(w, dtype=float)
    if w.sum() == 0:
        return w
    w = w / w.sum()
    for _ in range(it):
        over = w > cap + 1e-12
        if not over.any():
            break
        ex = (w[over] - cap).sum()
        w[over] = cap
        if w[~over].sum() > 0:
            w[~over] += ex * w[~over] / w[~over].sum()
    return w

def select(df, n, score="score", prev=(), buffer=None, ind=None, ind_cap=0.30, ind_cap_unknown=0.15):
    """依分數排序挑 n 檔。
    buffer=K：上期持股只要仍在前 K 名（含第 K 名）就續抱，空位再由高分補滿。
    產業上限：未知 15%（floor），其他 30%。「未知」是正常產業桶，受上限而非直接剔除。
    回傳 (codes, rank_map, notes)。
    rank_map 為流動性篩選後、產業上限前的原始名次（1-based）。
    """
    if len(df) == 0 or n <= 0:
        return [], {}, {}
    d = df.sort_values(score, ascending=False).reset_index(drop=True)
    codes = list(d.code)
    rank = {c: i + 1 for i, c in enumerate(codes)}
    keep = [c for c in prev if c in rank and (buffer is None or rank[c] <= buffer)]
    keep = sorted(keep, key=lambda c: rank[c])
    out = []
    cnt = {}
    notes = {}
    mx_other = int(np.floor(ind_cap * n)) if ind_cap else None
    mx_unk = int(np.floor(ind_cap_unknown * n)) if ind_cap_unknown else None
    candidates = keep + [c for c in codes if c not in keep]
    for c in candidates:
        if len(out) >= n:
            break
        if c in out:
            continue
        g = (ind or {}).get(c, "未知")
        if g is None or (isinstance(g, float) and np.isnan(g)):
            g = "未知"
        is_keep = c in keep
        current = cnt.get(g, 0)
        if g == "未知":
            if mx_unk is not None and current >= mx_unk:
                continue
        else:
            if mx_other is not None and current >= mx_other:
                continue
        if not is_keep and rank.get(c, 999) > n:
            notes[c] = "產業上限遞補"
        out.append(c)
        cnt[g] = current + 1
    return out, rank, notes

def weights(df, codes, scheme="ew", cap=0.10):
    if not codes:
        return pd.Series(dtype=float)
    if scheme == "ew":
        w = pd.Series(1.0, index=codes)
    else:
        s = df.set_index("code").loc[codes, "score"].rank()
        w = s
    return cap_weights(w, cap) if len(codes) * cap >= 1 else w / w.sum()
