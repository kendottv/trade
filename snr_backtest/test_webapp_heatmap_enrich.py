#!/usr/bin/env python3
"""離線 mock 測試：報價逾時、非當日、stale、產業對照、真路徑 20 檔快報價。不連網、不讀 secrets。"""
import sys
import time
import threading
from unittest.mock import patch, MagicMock
from datetime import datetime
from zoneinfo import ZoneInfo
import types

import webapp

TAIPEI = ZoneInfo("Asia/Taipei")

def _install_fake_quotes(sleep_s=0.0):
    """在 sys.modules 注入輕量假 quotes，避免真實 quotes 依賴 pandas。"""
    fake = types.ModuleType("quotes")
    def get_feed():
        feed = MagicMock()
        def last(code):
            if sleep_s:
                time.sleep(sleep_s)
            q = MagicMock()
            q.last = 100.0
            q.prev_close = 90.0
            q.ts = datetime.now(TAIPEI)
            q.source = "mock"
            return q
        feed.last.side_effect = last
        return feed
    fake.get_feed = get_feed
    fake.now_taipei = lambda: datetime.now(TAIPEI)
    old = sys.modules.get("quotes")
    sys.modules["quotes"] = fake
    return old

def _restore_quotes(old):
    if old is None:
        sys.modules.pop("quotes", None)
    else:
        sys.modules["quotes"] = old

def test_non_today_quote():
    with patch("webapp._safe_quote") as mq:
        q = MagicMock()
        q.last = 100
        q.prev_close = 90
        q.ts = datetime.now(TAIPEI).replace(day=1)
        mq.return_value = q
        pos = {"code": "2330", "last": 100, "avg": 90, "mv": 10000}
        out = webapp._enrich_pos_display(pos, is_paper=True)
        assert out["day_chg"] is None, "非當日報價不得冒充今日漲跌"

def test_single_timeout_caches():
    with patch("webapp._fetch_quote_raw", side_effect=TimeoutError("slow")):
        webapp._QUOTE_CACHE.clear()
        r1 = webapp._safe_quote("SLOW")
        assert r1 is None
        assert "SLOW" in webapp._QUOTE_CACHE
        r2 = webapp._safe_quote("SLOW")
        assert r2 is None

def test_batch_timeout():
    positions = [{"code": f"T{i}", "last": 10, "avg": 10, "mv": 1000} for i in range(20)]
    def slow(_code):
        time.sleep(2.5)
        return None
    with patch("webapp._fetch_quote_raw", side_effect=slow):
        t0 = time.time()
        webapp._enrich_positions_batch(positions)
        elapsed = time.time() - t0
        assert elapsed < 10.0, f"批次逾時 {elapsed:.1f}s > 10s"
        assert all("day_chg" in p for p in positions)

def test_real_path_20_fast():
    """只 mock 底層 get_feed().last（透過 sys.modules 假 quotes）；保留真實路徑。assert 全部 20。"""
    old = _install_fake_quotes(sleep_s=0.05)
    try:
        positions = [{"code": f"F{i}", "last": 100, "avg": 90, "mv": 10000} for i in range(20)]
        t0 = time.time()
        webapp._enrich_positions_batch(positions)
        elapsed = time.time() - t0
        assert elapsed < webapp._BATCH_QUOTE_TIMEOUT + 1.0
        valid = sum(1 for p in positions if p.get("day_chg") is not None)
        assert valid == 20, f"only {valid}/20 got day_chg"
        assert all(p["code"] in webapp._QUOTE_CACHE for p in positions)
        # 結束後無 done future 殘留，sem 回到上限
        with webapp._inflight_lock:
            done_left = [f for f in webapp._inflight.values() if f.done()]
        assert not done_left, "done futures left in _inflight"
        assert webapp._slot_sem._value == webapp._MAX_SLOTS
    finally:
        _restore_quotes(old)

def test_immediate_return_no_deadlock():
    """立刻回的 last，覆蓋同步 callback 路徑，必須在 5 秒內結束。"""
    old = _install_fake_quotes(sleep_s=0.0)
    try:
        positions = [{"code": "IMM", "last": 100, "avg": 90, "mv": 1000}]
        t0 = time.time()
        webapp._enrich_positions_batch(positions)
        elapsed = time.time() - t0
        assert elapsed < 5.0
        with webapp._inflight_lock:
            done_left = [f for f in webapp._inflight.values() if f.done()]
        assert not done_left
    finally:
        _restore_quotes(old)

def test_safe_quote_bounded():
    """多輪永不返回的 last + 等到逾時後，running+queued 有界。"""
    stop = threading.Event()
    def never(_code):
        stop.wait(timeout=30)
        return None
    with patch("webapp._fetch_quote_raw", side_effect=never):
        webapp._QUOTE_CACHE.clear()
        codes1 = [f"H1{i}" for i in range(6)]
        threads1 = [threading.Thread(target=lambda cc=c: webapp._safe_quote(cc)) for c in codes1]
        for t in threads1:
            t.start()
        time.sleep(webapp._QUOTE_TIMEOUT + 0.5)
        codes2 = [f"H2{i}" for i in range(6)]
        threads2 = [threading.Thread(target=lambda cc=c: webapp._safe_quote(cc)) for c in codes2]
        for t in threads2:
            t.start()
        time.sleep(1.0)
        with webapp._inflight_lock:
            live = len([f for f in webapp._inflight.values() if not f.done()])
        assert live <= webapp._MAX_SLOTS, f"live inflight {live} > {webapp._MAX_SLOTS}"
        assert webapp._slot_sem._value <= webapp._MAX_SLOTS
        stop.set()
        for t in threads1 + threads2:
            t.join(timeout=1.0)

def test_stale_threshold():
    assert webapp._sim_snapshot_stale(301, True) is True
    assert webapp._sim_snapshot_stale(299, True) is False
    assert webapp._sim_snapshot_stale(3601, False) is True
    assert webapp._sim_snapshot_stale(3599, False) is False

def test_industry_from_target():
    with patch("nn_strategy.latest_target") as lt:
        lt.return_value = ("2026-11", [{"code": "2330", "industry": "半導體"}])
        pos = {"code": "2330", "industry": "未知", "last": 100, "avg": 90, "mv": 1000}
        out = webapp._enrich_pos_display(pos, is_paper=False, prefetched_quote=None, quote_provided=True)
        assert out["industry"] == "半導體"
    with patch("nn_strategy.latest_target") as lt:
        lt.return_value = ("2026-11", [{"code": "OTHER", "industry": "電子"}])
        pos = {"code": "MISSING", "industry": "未知", "last": 100, "avg": 90, "mv": 1000}
        out = webapp._enrich_pos_display(pos, is_paper=False, prefetched_quote=None, quote_provided=True)
        assert out["industry"] == "未知"

if __name__ == "__main__":
    test_non_today_quote()
    test_single_timeout_caches()
    test_batch_timeout()
    test_real_path_20_fast()
    test_immediate_return_no_deadlock()
    test_safe_quote_bounded()
    test_stale_threshold()
    test_industry_from_target()
    print("ALL ENRICH TESTS PASS")
    sys.exit(0)
