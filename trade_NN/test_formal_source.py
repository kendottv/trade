"""回歸測試：真正呼叫 paper_trade.main，證明實際產出的 paper_target 選股名次與 score
來自 preds_tf_real.pkl 的 TF-NN3，而非 live_preds_all.csv 的獨立分數。
全部使用 tempfile fixtures + 注入產業／名稱路徑，不讀真的 data/out/帳本，不連網。
mock 通知；缺檔／月份錯誤時驗證 nonzero、通知恰一次、既有 target 與假帳本 bytes/hash 完全不變。
執行：python trade_NN/test_formal_source.py
"""
import os, sys, tempfile, shutil, hashlib, sqlite3, pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import paper_trade

def mock_notify(msg):
    print(f"[MOCK NOTIFY] {msg}")
    mock_notify.calls.append(msg)
mock_notify.calls = []

def sha256(path):
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()

def make_fake_panel(mon, codes):
    rows = []
    for c in codes:
        rows.append({
            "mon": pd.Timestamp(mon + "-01"),
            "code": c,
            "name": c,
            "close": 100.0,
            "dv": 1e9,
            "mcap": 1e9,
            "beta": 1.0,
            "ret": 0.01,
            "ret_next": 0.02
        })
    return pd.DataFrame(rows)

def test_formal_drives_real_target():
    tmp = tempfile.mkdtemp(prefix="formal_main_")
    try:
        mon = "2026-10"
        codes = ["A", "B", "C", "D"]
        # 假 panel
        panel = make_fake_panel(mon, codes)
        panel_path = os.path.join(tmp, "panel.pkl")
        panel.to_pickle(panel_path)
        # 假 industry（注入用）
        ind_path = os.path.join(tmp, "industry.csv")
        pd.DataFrame({"code": codes, "name": codes, "market": ["TW"]*4, "industry": ["未知"]*4}).to_csv(ind_path, index=False)
        # 假 names
        names_path = os.path.join(tmp, "stock_names.csv")
        pd.DataFrame({"code": codes, "name": codes}).to_csv(names_path, index=False)
        # 衝突：live 把 A 排最高；real 把 B 排最高
        live_path = os.path.join(tmp, "live_preds_all.csv")
        pd.DataFrame({
            "mon": [mon]*4,
            "code": codes,
            "pred_excess_ret": [100.0, 10.0, 5.0, 1.0]
        }).to_csv(live_path, index=False)
        real_path = os.path.join(tmp, "preds_tf_real.pkl")
        formal_scores = {"A": 1.0, "B": 100.0, "C": 50.0, "D": 20.0}
        pd.DataFrame({
            "mon": pd.to_datetime([mon+"-01"]*4),
            "code": codes,
            "TF-NN3": [formal_scores[c] for c in codes],
            "ret_next": [0.0]*4, "rn": [0.0]*4, "y": [0.0]*4, "mcap": [1e9]*4
        }).to_pickle(real_path)
        # 假 ledger
        db_path = os.path.join(tmp, "paper_ledger.db")
        # 既有 target
        out_dir = os.path.join(tmp, "out")
        os.makedirs(out_dir, exist_ok=True)
        existing_target = os.path.join(out_dir, f"paper_target_{mon}.csv")
        pd.DataFrame({"code": ["OLD"], "score": [0.0]}).to_csv(existing_target, index=False)
        # 呼叫真正的 main（注入所有路徑）
        mock_notify.calls.clear()
        rc = paper_trade.main(
            live_path=live_path, real_path=real_path, panel_path=panel_path,
            out_dir=out_dir, db_path=db_path,
            industry_path=ind_path, names_path=names_path,
            notifier=mock_notify, nav=1_000_000
        )
        assert rc == 0, f"main 應成功，實際 {rc}"
        # 讀實際產生的 target
        target = pd.read_csv(os.path.join(out_dir, f"paper_target_{mon}.csv"), dtype={"code": str})
        assert len(target) > 0, "應產生 target"
        # 明確斷言：選出的是 formal 最高分的，score 與 filtered_rank 來自 formal
        # formal 排序：B(100) > C(50) > D(20) > A(1)
        expected_order = ["B", "C", "D", "A"]
        for _, row in target.iterrows():
            assert abs(row["score"] - formal_scores[row["code"]]) < 1e-6, f"score 應來自 formal，實際 {row['score']}"
        selected = list(target.sort_values("filtered_rank")["code"])
        # 至少前幾名必須是 formal 最高的
        assert selected[0] == "B", f"filtered_rank 1 應為 formal 最高的 B，實際 {selected}"
        assert "A" not in selected[:2], "live 高分的 A 不應排在 formal 前面"
        print("回歸測試通過：實際 paper_target 的選股、filtered_rank 與 score 來自正式 TF-NN3")
        # ---- 失敗情境 ----
        def assert_unchanged(target_path, db_path, before_target_hash, before_db_hash):
            after_target = sha256(target_path)
            after_db = sha256(db_path)
            assert after_target == before_target_hash, "失敗時 target bytes/hash 必須完全不變"
            assert after_db == before_db_hash, "失敗時 ledger bytes/hash 必須完全不變"
        # 1) 缺檔
        before_t = sha256(existing_target)
        before_d = sha256(db_path)
        mock_notify.calls.clear()
        rc_fail = paper_trade.main(live_path=os.path.join(tmp, "missing.csv"), real_path=real_path,
                                   panel_path=panel_path, out_dir=out_dir, db_path=db_path,
                                   industry_path=ind_path, names_path=names_path, notifier=mock_notify)
        assert rc_fail != 0
        assert len(mock_notify.calls) == 1
        assert_unchanged(existing_target, db_path, before_t, before_d)
        print("缺檔情境通過")
        # 2) 月份不符
        bad_live = os.path.join(tmp, "bad_mon.csv")
        pd.DataFrame({"mon": ["2026-09"], "code": ["A"], "pred_excess_ret": [1.0]}).to_csv(bad_live, index=False)
        before_t = sha256(existing_target)
        before_d = sha256(db_path)
        mock_notify.calls.clear()
        rc_fail = paper_trade.main(live_path=bad_live, real_path=real_path, panel_path=panel_path,
                                   out_dir=out_dir, db_path=db_path,
                                   industry_path=ind_path, names_path=names_path, notifier=mock_notify)
        assert rc_fail != 0
        assert len(mock_notify.calls) == 1
        assert_unchanged(existing_target, db_path, before_t, before_d)
        print("月份不符情境通過")
        # 3) 格式錯誤
        bad_fmt = os.path.join(tmp, "bad_fmt.csv")
        pd.DataFrame({"mon": ["bad"], "code": ["A"], "pred_excess_ret": [1.0]}).to_csv(bad_fmt, index=False)
        before_t = sha256(existing_target)
        before_d = sha256(db_path)
        mock_notify.calls.clear()
        rc_fail = paper_trade.main(live_path=bad_fmt, real_path=real_path, panel_path=panel_path,
                                   out_dir=out_dir, db_path=db_path,
                                   industry_path=ind_path, names_path=names_path, notifier=mock_notify)
        assert rc_fail != 0
        assert len(mock_notify.calls) == 1
        assert_unchanged(existing_target, db_path, before_t, before_d)
        print("格式錯誤情境通過")
        print("全部失敗情境通過：nonzero、通知恰一次、target 與 ledger bytes/hash 完全不變")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    test_formal_drives_real_target()
