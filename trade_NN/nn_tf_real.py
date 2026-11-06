"""正式訊號月預測（v5）：最終模型對所有有特徵的股票／月份評分（含無下月報酬的最新月）。
只有訓練與驗證才使用 y 非 NaN 的列。評分對所有有特徵的列（含無 ret_next）。
特徵在進模型前不得有 NaN。輸出 out/preds_tf_real.pkl。
nn_tf.py 僅歷史比較。下市股以 −100% 計（在後續回測處理）。不改模型或特徵。
資料路徑由環境變數 PANEL_PATH 決定。
"""
import os, numpy as np, pandas as pd
from nn_tf import FEAT, fit_ensemble, PANEL_PATH

P = pd.read_pickle(PANEL_PATH)
P = P.dropna(subset=["mcap", "mom_12"])
# 不做 mon 上限截斷，保留所有有特徵的月份（含 2026-09、2026-10）
L = P.dropna(subset=["ret_next"])
L_rn = L.groupby("mon")["ret_next"].transform(lambda s: s.clip(s.quantile(.025), s.quantile(.975)))
mk = L.groupby("mon").apply(lambda d: np.average(d["ret_next"], weights=d["mcap"]))
P["rn"] = L_rn.reindex(P.index)
P["y"] = P["rn"] - P["mon"].map(mk)
for c in FEAT:
    s = P[c].replace([np.inf, -np.inf], np.nan)
    s = s.groupby(P["mon"]).transform(lambda x: x.clip(x.quantile(.01), x.quantile(.99)))
    P[c] = s.groupby(P["mon"]).transform(lambda x: (x - x.mean()) / x.std()).fillna(0)
P = P.sort_values(["mon", "code"]).reset_index(drop=True)
# 訓練用月份：只保留有足夠有標籤樣本的月份
months = sorted(P.dropna(subset=["y"])["mon"].unique())
T = len(months)
ntr, nva = int(round(.3 * T)), int(round(.2 * T))
k0 = ntr + nva
print("train_months", T, "test_first", months[k0].date() if k0 < T else None, flush=True)
log = []
final_model = None
for k in range(k0, T, 12):
    te, va, tr = months[k:k + 12], months[k - nva:k], months[:k - nva]
    # 訓練與驗證只用 y 非 NaN 的列
    Dtr = P[P.mon.isin(tr)].dropna(subset=["y"])
    Dva = P[P.mon.isin(va)].dropna(subset=["y"])
    if len(Dtr) == 0 or len(Dva) == 0:
        continue
    f32 = lambda d: d[FEAT].values.astype("float32")
    best = None
    for l1 in (1e-5, 1e-4, 1e-3):
        f = fit_ensemble(f32(Dtr), Dtr.y.values.astype("float32"), f32(Dva), Dva.y.values.astype("float32"), l1)
        pred_va = f(f32(Dva))
        mse = float(np.mean((pred_va - Dva.y.values) ** 2))
        if best is None or mse < best[0]:
            best = (mse, l1, f)
    if best is not None:
        final_model = best[2]
        log.append({"test_start": str(te[0].date()), "l1": best[1], "val_mse": best[0]})
        print(log[-1], flush=True)
# 用最終模型對全部有特徵的資料打分（含最新無標籤月份）
os.makedirs("out", exist_ok=True)
if final_model is not None:
    # 確保特徵無 NaN
    X_all = P[FEAT].fillna(0).values.astype("float32")
    o = P[["mon", "code", "ret_next", "rn", "y", "mcap"]].copy()
    o["TF-NN3"] = final_model(X_all)
    o.to_pickle("out/preds_tf_real.pkl")
    pd.DataFrame(log).to_csv("out/tf_hyperparams_real.csv", index=False)
    print("已寫入 out/preds_tf_real.pkl，含所有有特徵月份（含無 ret_next 最新月）")
else:
    print("無模型可打分")
