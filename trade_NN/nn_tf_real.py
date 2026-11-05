"""nn_tf.py 的「現實版」：訓練/驗證完全照舊（需要已實現的 y），
但測試月份對『所有有特徵的股票』都打分（含下個月下市/停牌、ret_next 缺值者），
避免用未來資訊把要下市的股票事先剔除。
輸出 out/preds_tf_real.pkl、out/tf_hyperparams_real.csv。
規格 v4 AC-1。不改模型或特徵。
"""
import os, numpy as np, pandas as pd
from nn_tf import FEAT, fit_ensemble

SRC = "."
P = pd.read_pickle(f"{SRC}/data/panel.pkl")
P = P.dropna(subset=["mcap", "mom_12"])
P = P[P["mon"] <= pd.Timestamp("2026-08-31")].copy()
L = P.dropna(subset=["ret_next"])
L_rn = L.groupby("mon")["ret_next"].transform(lambda s: s.clip(s.quantile(.025), s.quantile(.975)))
mk = L.groupby("mon").apply(lambda d: np.average(d["ret_next"], weights=d["mcap"]))
P["rn"] = L_rn.reindex(P.index)
P["y"] = P["rn"] - P["mon"].map(mk)
P = P[P["mon"].map(L.groupby("mon").size()).fillna(0) >= 100]
for c in FEAT:
    s = P[c].replace([np.inf, -np.inf], np.nan)
    s = s.groupby(P["mon"]).transform(lambda x: x.clip(x.quantile(.01), x.quantile(.99)))
    P[c] = s.groupby(P["mon"]).transform(lambda x: (x - x.mean()) / x.std()).fillna(0)
P = P.sort_values(["mon", "code"]).reset_index(drop=True)
months = sorted(P["mon"].unique())
T = len(months)
ntr, nva = int(round(.3 * T)), int(round(.2 * T))
k0 = ntr + nva
print("months", T, "test_first", months[k0].date(), flush=True)
outs = []
log = []
for k in range(k0, T, 12):
    te, va, tr = months[k:k + 12], months[k - nva:k], months[:k - nva]
    Dtr = P[P.mon.isin(tr)].dropna(subset=["y"])
    Dva = P[P.mon.isin(va)].dropna(subset=["y"])
    Dte = P[P.mon.isin(te)]
    f32 = lambda d: d[FEAT].values.astype("float32")
    best = None
    for l1 in (1e-5, 1e-4, 1e-3):
        f = fit_ensemble(f32(Dtr), Dtr.y.values.astype("float32"), f32(Dva), Dva.y.values.astype("float32"), l1)
        mse = float(np.mean((f(f32(Dva)) - Dva.y.values) ** 2))
        if best is None or mse < best[0]:
            best = (mse, l1, f)
    o = Dte[["mon", "code", "ret_next", "rn", "y", "mcap"]].copy()
    o["TF-NN3"] = best[2](f32(Dte))
    outs.append(o)
    log.append({"test_start": str(te[0].date()), "l1": best[1], "val_mse": best[0],
                "n_test": len(o), "n_test_no_label": int(o.ret_next.isna().sum())})
    print(log[-1], flush=True)
pd.concat(outs).to_pickle("out/preds_tf_real.pkl")
pd.DataFrame(log).to_csv("out/tf_hyperparams_real.csv", index=False)
