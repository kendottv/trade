"""【LEGACY】佳必琪(6197) NN 量化專案 — TensorFlow/Keras 版 NN3
此為舊版（非 real 口徑）。正式回測請改用 nn_tf_real.py + backtest_real.py。
規格 v3 AC-3：舊輸出標為 legacy。
資料：沿用本機 data/panel.pkl（gitignore 排除），前處理與切分完全照舊：
  y = 下月含息報酬(每月2.5%縮尾) − 樣本市值加權市場報酬
  X = 14 個價量特徵，每月 1/99% 縮尾後 z-score，缺值補 0
  切分 30/20/50：訓練 2001/09–2009/02、驗證 2009/03–2014/02、測試 2014/03–2026/08，每 12 個月擴張式重訓
"""
import os, numpy as np, pandas as pd, tensorflow as tf
from tensorflow import keras

FEAT = "mom_1,mom_6,mom_12,mom_36,chmom_6,retvol,maxret,mvel1,dolvol,turn,stdturn,stddolvol,ill,beta".split(",")


def load_panel():
    """讀 panel 並做和 run_models.py 一模一樣的前處理（只用 t 月以前的資訊，沒有 look-ahead）。"""
    P = pd.read_pickle("data/panel.pkl")
    P = P.dropna(subset=["ret_next", "mcap", "mom_12"])
    P = P[P["mon"] <= pd.Timestamp("2026-08-31")]
    P["rn"] = P.groupby("mon")["ret_next"].transform(lambda s: s.clip(s.quantile(.025), s.quantile(.975)))
    mk = P.groupby("mon").apply(lambda d: np.average(d["ret_next"], weights=d["mcap"]))
    P["mkt_next"] = P["mon"].map(mk)
    P["y"] = P["rn"] - P["mkt_next"]
    P = P[P["mon"].map(P.groupby("mon").size()) >= 100]
    for c in FEAT:
        s = P[c].replace([np.inf, -np.inf], np.nan)
        s = s.groupby(P["mon"]).transform(lambda x: x.clip(x.quantile(.01), x.quantile(.99)))
        P[c] = s.groupby(P["mon"]).transform(lambda x: (x - x.mean()) / x.std()).fillna(0)
    return P.sort_values(["mon", "code"]).reset_index(drop=True)


def build_nn3(n_in, l1=1e-5, lr=1e-3, seed=0):
    """NN3：32-16-8，每層 Dense → BatchNorm → ReLU，權重加 L1 懲罰（論文 / GKX 作法）。"""
    keras.utils.set_random_seed(seed)
    reg = keras.regularizers.l1(l1)
    inp = keras.Input((n_in,))
    x = inp
    for h in (32, 16, 8):
        x = keras.layers.Dense(h, kernel_regularizer=reg)(x)
        x = keras.layers.BatchNormalization()(x)
        x = keras.layers.Activation("relu")(x)
    out = keras.layers.Dense(1)(x)
    m = keras.Model(inp, out)
    m.compile(keras.optimizers.Adam(lr), loss="mse")
    return m


def fit_ensemble(Xtr, ytr, Xva, yva, l1, seeds=5):
    """同一組超參數訓練 5 個不同 seed，驗證集 early stopping，預測取平均。"""
    ms = []
    for s in range(seeds):
        m = build_nn3(Xtr.shape[1], l1=l1, seed=s)
        m.fit(Xtr, ytr, validation_data=(Xva, yva), epochs=100, batch_size=2048, verbose=0,
              callbacks=[keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True)])
        ms.append(m)
    return lambda X: np.mean([m.predict(X, batch_size=8192, verbose=0).ravel() for m in ms], 0)


if __name__ == "__main__":
    P = load_panel()
    months = sorted(P["mon"].unique())
    T = len(months)
    ntr, nva = int(round(.3 * T)), int(round(.2 * T))
    k0 = ntr + nva
    print("months", T, "train_end", months[ntr - 1].date(), "val_end", months[k0 - 1].date(), "test_first", months[k0].date(), flush=True)
    outs = []
    log = []
    for k in range(k0, T, 12):
        te, va, tr = months[k:k + 12], months[k - nva:k], months[:k - nva]
        D = {n: P[P["mon"].isin(s)] for n, s in [("tr", tr), ("va", va), ("te", te)]}
        X = {n: d[FEAT].values.astype("float32") for n, d in D.items()}
        y = {n: d["y"].values.astype("float32") for n, d in D.items()}
        best = None
        for l1 in (1e-5, 1e-4, 1e-3):
            f = fit_ensemble(X["tr"], y["tr"], X["va"], y["va"], l1)
            mse = float(np.mean((f(X["va"]) - y["va"]) ** 2))
            if best is None or mse < best[0]:
                best = (mse, l1, f)
        o = D["te"][["mon", "code", "ret_next", "rn", "y", "mcap"]].copy()
        o["TF-NN3"] = best[2](X["te"])
        outs.append(o)
        log.append({"test_start": str(te[0].date()), "l1": best[1], "val_mse": best[0]})
        print(log[-1], flush=True)
    os.makedirs("out", exist_ok=True)
    pd.concat(outs).to_pickle("out/preds_tf.pkl")
    pd.DataFrame(log).to_csv("out/tf_hyperparams.csv", index=False)
