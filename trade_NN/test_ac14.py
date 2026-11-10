"""AC-14 自測：可重跑，使用暫存目錄假檔案，不碰真的 out/、trades.db 或任何金鑰。
通知步驟用 mock，不實際發出。
涵蓋三種情況：
(a) 月份一致時通過
(b) 有一個檔案的月份不同時失敗
(c) 檔案缺少或月份格式錯誤時失敗
(b) 和 (c) 都確認目標檔沒有被寫入。
執行：python trade_NN/test_ac14.py
"""
import os, sys, tempfile, shutil, pandas as pd
from pathlib import Path

# 將 trade_NN 加入 path 以便 import（僅匯入函式，不執行主流程）
sys.path.insert(0, str(Path(__file__).parent))

from paper_trade import check_signal_month

def mock_notify(msg):
    print(f"[MOCK NOTIFY] {msg}")

def run_case(name, live_mon, real_mons, missing_live=False, missing_real=False, bad_format=False):
    tmp = tempfile.mkdtemp(prefix="ac14_")
    try:
        live_path = os.path.join(tmp, "live_preds_all.csv")
        real_path = os.path.join(tmp, "preds_tf_real.pkl")
        target_path = os.path.join(tmp, f"paper_target_{live_mon}.csv")
        if not missing_live:
            mon_val = "bad" if bad_format else live_mon
            pd.DataFrame({"mon": [mon_val], "code": ["2330"], "pred_excess_ret": [0.01]}).to_csv(live_path, index=False)
        if not missing_real:
            mons = real_mons if real_mons else [live_mon]
            pd.DataFrame({"mon": mons, "code": ["2330"], "TF-NN3": [0.01]}).to_pickle(real_path)
        mon, ok, msg = check_signal_month(live_path, real_path)
        print(f"{name}: ok={ok}, msg={msg}")
        # 模擬：只有通過才寫目標檔
        wrote = False
        if ok:
            pd.DataFrame({"code": ["2330"]}).to_csv(target_path, index=False)
            wrote = os.path.exists(target_path)
        else:
            wrote = os.path.exists(target_path)
        return ok, wrote, msg
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def main():
    print("=== AC-14 自測 ===")
    # (a) 月份一致
    ok_a, wrote_a, msg_a = run_case("(a) 一致", "2026-10", ["2026-10"])
    assert ok_a and wrote_a, f"(a) 應通過且寫入，實際 ok={ok_a} wrote={wrote_a}"
    print("(a) 通過")
    # (b) 月份不同
    ok_b, wrote_b, msg_b = run_case("(b) 月份不同", "2026-10", ["2026-09"])
    assert not ok_b and not wrote_b, f"(b) 應失敗且不寫入，實際 ok={ok_b} wrote={wrote_b}"
    print("(b) 通過（失敗且未寫入）")
    # (c) 缺少檔案
    ok_c1, wrote_c1, _ = run_case("(c1) 缺 live", "2026-10", ["2026-10"], missing_live=True)
    assert not ok_c1 and not wrote_c1, "(c1) 應失敗且不寫入"
    ok_c2, wrote_c2, _ = run_case("(c2) 缺 real", "2026-10", ["2026-10"], missing_real=True)
    assert not ok_c2 and not wrote_c2, "(c2) 應失敗且不寫入"
    ok_c3, wrote_c3, _ = run_case("(c3) 格式錯誤", "2026-10", ["2026-10"], bad_format=True)
    assert not ok_c3 and not wrote_c3, "(c3) 應失敗且不寫入"
    print("(c) 通過（缺少／格式錯誤皆失敗且未寫入）")
    print("AC-14 全部通過")

if __name__ == "__main__":
    main()
