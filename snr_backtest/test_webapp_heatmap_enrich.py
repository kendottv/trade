#!/usr/bin/env python3
"""離線 mock 測試：報價逾時、非當日、stale、產業對照。不連網、不讀 secrets。"""
import sys
import time
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

import webapp

def test_non_today_quote():
    with patch("webapp._safe_quote") as mq:
        q = MagicMock()
        q.last = 100
        q.prev_close = 90
        q.ts = datetime.now() - timedelta(days=1)
        mq.return_value = q
        pos = {"code": "2330", "last": 100, "avg": 90, "mv": 10000}
        out = webapp._enrich_pos_display(pos, is_paper=True)
        assert out["day_chg"] is None, "非當日報價不得冒充今日漲跌"

def test_single_timeout_caches():
    with patch("webapp._executor") as ex:
        fut = MagicMock()
        fut.result.side_effect = webapp.FutTimeout()
        ex.submit.return_value = fut
        webapp._QUOTE_CACHE.clear()
        r1 = webapp._safe_quote("SLOW")
        assert r1 is None
        assert "SLOW" in webapp._QUOTE_CACHE
        r2 = webapp._safe_quote("SLOW")
        assert r2 is None
        assert ex.submit.call_count == 1

def test_batch_timeout():
    positions = [{"code": f"T{i}", "last": 10, "avg": 10, "mv": 1000} for i in range(20)]
    def slow(_code):
        time.sleep(2.5)
        return None
    with patch("webapp._safe_quote", side_effect=slow):
        t0 = time.time()
        webapp._enrich_positions_batch(positions)
        elapsed = time.time() - t0
        assert elapsed < 10.0, f"批次逾時 {elapsed:.1f}s > 10s"
        assert all("day_chg" in p for p in positions)

def test_stale_threshold():
    # 呼叫 webapp 實際抽出的函式
    assert webapp._sim_snapshot_stale(301, True) is True
    assert webapp._sim_snapshot_stale(299, True) is False
    assert webapp._sim_snapshot_stale(3601, False) is True
    assert webapp._sim_snapshot_stale(3599, False) is False

def test_industry_from_target():
    with patch("nn_strategy.latest_target") as lt:
        lt.return_value = ("2026-11", [{"code": "2330", "industry": "半導體"}])
        pos = {"code": "2330", "industry": "未知", "last": 100, "avg": 90, "mv": 1000}
        out = webapp._enrich_pos_display(pos, is_paper=False)
        assert out["industry"] == "半導體"
    with patch("nn_strategy.latest_target") as lt:
        lt.return_value = ("2026-11", [{"code": "OTHER", "industry": "電子"}])
        pos = {"code": "MISSING", "industry": "未知", "last": 100, "avg": 90, "mv": 1000}
        out = webapp._enrich_pos_display(pos, is_paper=False)
        assert out["industry"] == "未知"

if __name__ == "__main__":
    test_non_today_quote()
    test_single_timeout_caches()
    test_batch_timeout()
    test_stale_threshold()
    test_industry_from_target()
    print("ALL ENRICH TESTS PASS")
    sys.exit(0)
