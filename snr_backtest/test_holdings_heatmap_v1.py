#!/usr/bin/env python3
"""離線假資料驗證持股熱力圖顯示邏輯。不連網、不讀真實 DB/secrets。"""
import sys
from holdings_heatmap import holdings_share, day_change, buy_pnl_pct, valid_mv, layout_tiles

def test_share_error():
    pos = [{"code": "A", "mv": 100}, {"code": "B", "mv": 50}, {"code": "C", "mv": 0}]
    sh = holdings_share(pos)
    assert abs(sh["A"] - 2/3) < 0.01, "AC-3 面積占比誤差應 ≤1 百分點"
    assert "C" not in sh

def test_layout_area():
    pos = [
        {"code": "A", "mv": 100, "industry": "半導體"},
        {"code": "B", "mv": 50, "industry": "半導體"},
        {"code": "C", "mv": 50, "industry": "電子"},
    ]
    tiles = layout_tiles(pos, width=800, height=400)
    total_area = sum(t["area"] for t in tiles)
    shares = holdings_share(pos)
    for t in tiles:
        area_share = t["area"] / total_area
        assert abs(area_share - shares[t["code"]]) <= 0.01, f"{t['code']} area share deviation >1pp"

def test_missing_to_dash():
    assert day_change(None, 10) is None
    assert buy_pnl_pct(10, 0) is None
    assert buy_pnl_pct(10, -1) is None
    assert not valid_mv(0)
    assert not valid_mv(None)

def test_empty():
    assert holdings_share([]) == {}
    assert layout_tiles([]) == []

def test_isolation():
    paper = [{"code": "P1", "mv": 10}]
    sim = [{"code": "S1", "mv": 20}]
    assert set(holdings_share(paper)) != set(holdings_share(sim))

def test_unalloc():
    pos = [{"code": "A", "mv": 100}, {"code": "B", "mv": 0}, {"code": "C", "mv": -5}]
    sh = holdings_share(pos)
    assert "A" in sh and "B" not in sh and "C" not in sh
    assert len([p for p in pos if not valid_mv(p["mv"])]) == 2

if __name__ == "__main__":
    test_share_error()
    test_layout_area()
    test_missing_to_dash()
    test_empty()
    test_isolation()
    test_unalloc()
    print("ALL PASS")
    sys.exit(0)
