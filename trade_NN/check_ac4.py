"""AC-4 測試：10 檔高分「未知」股票、n=20。
斷言選出 20 檔、未知恰為上限（floor(0.15*20)=3）、其他產業 ≤6。
「未知」必須被當成產業桶受 15% 上限，而非直接剔除。
逐步追蹤：liquidity_screen 後未知剩幾檔、排名後、產業上限後。
"""
import pandas as pd
from portfolio import select, liquidity_screen

def test_ac4():
    rows = []
    for i in range(10):
        rows.append({"code": f"U{i:02d}", "score": 100.0 - i, "dv": 1e9 + i, "mcap": 1e9 + i, "industry": "未知"})
    for i in range(40):
        ind = f"產業{i % 8}"
        rows.append({"code": f"O{i:02d}", "score": 70.0 - i * 0.5, "dv": 1e9 + 100 + i, "mcap": 1e9 + 100 + i, "industry": ind})
    df = pd.DataFrame(rows)
    u = liquidity_screen(df, q=0.2)
    unk_after_liq = int((u.industry == "未知").sum())
    print(f"liquidity_screen 後未知檔數：{unk_after_liq}")
    assert unk_after_liq >= 3, f"流動性篩選後未知不足：{unk_after_liq}"
    # 不傳 ind，讓 select 使用 df.industry 欄
    codes, rank_map, notes = select(u, 20, prev=[], buffer=40, ind=None, ind_cap=0.30, ind_cap_unknown=0.15)
    assert len(codes) == 20, f"應選出 20 檔，實際 {len(codes)}"
    selected = u.set_index("code").loc[codes]
    unk = int((selected.industry == "未知").sum())
    others = selected.groupby("industry").size()
    others_max = int(others[others.index != "未知"].max()) if len(others) else 0
    expected_unk = int(0.15 * 20)
    print(f"產業上限後未知檔數：{unk}（預期 {expected_unk}）")
    assert unk == expected_unk, f"未知應恰為上限 {expected_unk} 檔，實際 {unk}"
    assert others_max <= 6, f"其他產業超過 6 檔：{others_max}"
    print(f"AC-4 通過：選出 {len(codes)} 檔、未知 {unk} 檔（上限 {expected_unk}）、其他產業最多 {others_max} 檔")

if __name__ == "__main__":
    test_ac4()
