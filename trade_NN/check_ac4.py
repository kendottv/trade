"""AC-4 測試：10 檔高分「未知」股票、n=20。
斷言選出 20 檔、未知 ≤3、其他產業 ≤6。
"""
import pandas as pd
from portfolio import select, liquidity_screen

def test_ac4():
    # 建構測試資料：確保全部通過流動性篩選，且有足夠股票可選滿 20
    rows = []
    for i in range(10):
        rows.append({"code": f"U{i:02d}", "score": 100 - i, "dv": 1e10, "mcap": 1e10, "industry": "未知"})
    for i in range(40):
        ind = f"產業{i % 8}"
        rows.append({"code": f"O{i:02d}", "score": 90 - i * 0.5, "dv": 1e10, "mcap": 1e10, "industry": ind})
    df = pd.DataFrame(rows)
    u = liquidity_screen(df, q=0.0)  # 全部通過
    ind_map = dict(zip(df.code, df.industry))
    codes, rank_map, notes = select(u, 20, prev=[], buffer=40, ind=ind_map, ind_cap=0.30, ind_cap_unknown=0.15)
    assert len(codes) == 20, f"應選出 20 檔，實際 {len(codes)}"
    selected = df.set_index("code").loc[codes]
    unk = (selected.industry == "未知").sum()
    others = selected.groupby("industry").size()
    others_max = others[others.index != "未知"].max() if len(others) else 0
    assert unk <= 3, f"未知超過 3 檔：{unk}"
    assert others_max <= 6, f"其他產業超過 6 檔：{others_max}"
    print(f"AC-4 通過：選出 {len(codes)} 檔、未知 {unk} 檔、其他產業最多 {others_max} 檔")

if __name__ == "__main__":
    test_ac4()
