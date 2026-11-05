"""AC-4 測試：10 檔高分「未知」股票、n=20。
斷言選出的「未知」不超過 3 檔，其他產業不超過 6 檔。
"""
import pandas as pd
from portfolio import select, liquidity_screen

def test_ac4():
    # 建構測試資料：20 檔高分未知 + 其他產業
    rows = []
    for i in range(10):
        rows.append({"code": f"U{i:02d}", "score": 100 - i, "dv": 1e9, "mcap": 1e9, "industry": "未知"})
    for i in range(30):
        ind = f"產業{i % 5}"
        rows.append({"code": f"O{i:02d}", "score": 80 - i, "dv": 1e9, "mcap": 1e9, "industry": ind})
    df = pd.DataFrame(rows)
    u = liquidity_screen(df)  # 全部通過
    ind_map = dict(zip(df.code, df.industry))
    codes, rank_map, notes = select(u, 20, prev=[], buffer=40, ind=ind_map, ind_cap=0.30, ind_cap_unknown=0.15)
    selected = df.set_index("code").loc[codes]
    unk = (selected.industry == "未知").sum()
    others = selected.groupby("industry").size()
    others = others[others.index != "未知"].max() if len(others) else 0
    assert unk <= 3, f"未知超過 3 檔：{unk}"
    assert others <= 6, f"其他產業超過 6 檔：{others}"
    print(f"AC-4 通過：未知 {unk} 檔、其他產業最多 {others} 檔")

if __name__ == "__main__":
    test_ac4()
