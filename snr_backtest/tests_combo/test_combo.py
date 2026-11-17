"""Offline unit tests for trade-paper-combo v4 (AC-16).

Run from repo root:
  python -m unittest discover snr_backtest/tests_combo
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
import importlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class ComboTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.paper = Path(self.tmp.name) / "paper_nn"
        self.paper.mkdir()
        self.backup = Path(self.tmp.name) / "backups"
        self.backup.mkdir()
        self.nn_out = Path(self.tmp.name) / "nn_out"
        self.nn_out.mkdir()
        os.environ["PAPER_NN_DIR"] = str(self.paper)
        os.environ["PAPER_COMBO_BACKUP"] = str(self.backup)
        os.environ["NN_OUT_DIR"] = str(self.nn_out)
        # reload so modules pick up getenv paths
        import nn_paper
        import sim_trader
        import cta_a1
        import nn_strategy
        importlib.reload(nn_paper)
        importlib.reload(sim_trader)
        importlib.reload(cta_a1)
        importlib.reload(nn_strategy)
        self.nn_paper = nn_paper
        self.sim_trader = sim_trader
        self.cta_a1 = cta_a1
        # minimal account
        self.acct = {
            "cash": 1_000_000.0,
            "equity": 1_000_000.0,
            "initial_cash": 1_000_000.0,
            "positions": [],
            "pending": [],
            "strategy": "nn_top20_buf40_ind30",
            "created_at": "2026-11-01",
            "last_session": None,
            "last_target": None,
            "paper_only": True,
        }
        (self.paper / "account.json").write_text(json.dumps(self.acct), encoding="utf-8")
        (self.paper / "ledger.csv").write_text("date,ticker,action,reason,price,shares,cash,equity,snr\n", encoding="utf-8")
        (self.paper / "equity.csv").write_text("date,cash,market_value,equity\n", encoding="utf-8")
        (self.paper / "daily_log.md").write_text("# test\n", encoding="utf-8")
        # inject proc_lock for Linux
        import proc_lock
        proc_lock.acquire = lambda lock: True
        # fake shioaji for make_order / snapshot paths
        self._install_fake_shioaji()

    def tearDown(self):
        os.environ.pop("PAPER_NN_DIR", None)
        os.environ.pop("PAPER_COMBO_BACKUP", None)
        os.environ.pop("NN_OUT_DIR", None)
        sys.modules.pop("shioaji", None)
        self.tmp.cleanup()

    def _install_fake_shioaji(self):
        fake = MagicMock()
        fake.constant.Action.Buy = "Buy"
        fake.constant.Action.Sell = "Sell"
        fake.constant.StockPriceType.LMT = "LMT"
        fake.constant.OrderType.ROD = "ROD"
        fake.constant.StockOrderLot.IntradayOdd = "IntradayOdd"
        fake.constant.StockOrderLot.Common = "Common"
        fake.constant.Unit.Share = "Share"
        sys.modules["shioaji"] = fake

    def _write_target(self, mon: str, rows: list[dict]):
        p = self.nn_out / f"paper_target_{mon}.csv"
        import csv
        with p.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["code", "weight", "close", "rank", "score", "industry"])
            w.writeheader()
            w.writerows(rows)


class TestSignalTiming(ComboTestBase):
    def test_signal_used_next_day_stale_or_no_open_no_change(self):
        sig = {"date": "2026-11-17", "close": 25000, "ma200": 24000, "signal": "on", "source": "test", "stale": False}
        (self.paper / "a1_signal.json").write_text(json.dumps(sig), encoding="utf-8")
        with patch.object(self.nn_paper.tw_calendar, "is_trading_day", side_effect=lambda d: d.weekday() < 5):
            rec, stale, why = self.nn_paper._signal_for_day("2026-11-18")
            self.assertFalse(stale)
            self.assertEqual(rec["signal"], "on")
            sig["date"] = "2026-11-10"
            (self.paper / "a1_signal.json").write_text(json.dumps(sig), encoding="utf-8")
            rec2, stale2, why2 = self.nn_paper._signal_for_day("2026-11-18")
            self.assertTrue(stale2)
            self.assertIn("前一個交易日", why2)


class TestCutoverAndBackup(ComboTestBase):
    def test_no_cutover_before_new_target(self):
        with patch.object(self.nn_paper, "latest_target", return_value=None):
            self.nn_paper.daily()
        a = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        self.assertNotIn("combo_since", a)
        self.assertEqual(a["strategy"], "nn_top20_buf40_ind30")

    def test_cutover_writes_backup_and_manifest(self):
        rows = [{"code": "2330", "weight": 1.0, "close": 1000.0, "rank": 1, "score": 1.0, "industry": "SEMI"}]
        self._write_target("2026-12", rows)
        with patch.object(self.nn_paper, "fetch_closes", return_value={"2330": (1000.0, "test")}), \
             patch.object(self.nn_paper, "_equity", return_value=(0.0, 1_000_000.0)):
            self.nn_paper.daily()
        a = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        self.assertEqual(a["strategy"], "nn3_60_a1_40")
        self.assertIn("combo_since", a)
        self.assertIn("a1", a)
        backups = list(self.backup.glob("backup_pre_combo_*"))
        self.assertTrue(backups)
        man = (backups[0] / "manifest.txt").read_text(encoding="utf-8")
        self.assertIn("account.json", man)
        h = hashlib.sha256((backups[0] / "account.json").read_bytes()).hexdigest()
        self.assertIn(h, man)

    def test_backup_fail_no_cutover(self):
        rows = [{"code": "2330", "weight": 1.0, "close": 1000.0, "rank": 1, "score": 1.0, "industry": "SEMI"}]
        self._write_target("2026-12", rows)
        with patch.object(self.nn_paper, "_do_backup", return_value=False):
            with self.assertRaises(SystemExit):
                self.nn_paper.daily()
        a = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        self.assertNotIn("combo_since", a)


class TestRebalanceAndCash(ComboTestBase):
    def test_a1_cash_not_used_by_nn3(self):
        a = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        a["combo_since"] = "2026-11-18"
        a["strategy"] = "nn3_60_a1_40"
        a["a1"] = {"target_ntd": 400_000, "cash": 400_000, "shares": 0, "state": "cash"}
        a["cash"] = 1_000_000
        (self.paper / "account.json").write_text(json.dumps(a), encoding="utf-8")
        rows = [{"code": "2330", "weight": 1.0, "close": 100.0, "rank": 1, "score": 1.0, "industry": "SEMI"}]
        self._write_target("2026-12", rows)
        with patch.object(self.nn_paper, "fetch_closes", return_value={"2330": (100.0, "test")}):
            self.nn_paper.daily()
        a2 = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(a2["a1"]["cash"], 399_000)


class TestCosts(unittest.TestCase):
    def test_sell_tax_and_min_commission(self):
        from broker import sell_fill, buy_cost
        sf = sell_fill(100, 100.0, 0.001425, 20.0, 0.003)
        self.assertAlmostEqual(sf.tax, 100 * 100 * 0.003)
        self.assertGreaterEqual(sf.commission, 20.0)
        bc = buy_cost(1, 10.0, 0.001425, 20.0)
        self.assertGreaterEqual(bc, 10 + 20)


class TestAccountFields(ComboTestBase):
    def test_old_fields_and_0050_position(self):
        a = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        a["combo_since"] = "2026-11-18"
        a["a1"] = {"target_ntd": 400000, "cash": 0, "shares": 100, "state": "holding"}
        a["positions"].append({
            "ticker": "0050", "name": "元大台灣50", "shares": 100, "avg_price": 100.0,
            "entry_date": "2026-11-18", "entry_snr": None, "time_stop_count": 0,
            "trail_armed": False, "nn_rank": None, "nn_score": None, "industry": "ETF",
            "last": 100.0, "price_src": "open 2026-11-18"
        })
        (self.paper / "account.json").write_text(json.dumps(a), encoding="utf-8")
        loaded = self.nn_paper.load()
        for k in ("cash", "equity", "initial_cash", "positions", "pending", "strategy",
                  "created_at", "last_session", "last_target", "paper_only"):
            self.assertIn(k, loaded)
        p = next(p for p in loaded["positions"] if p["ticker"] == "0050")
        for k in ("ticker", "name", "shares", "avg_price", "entry_date", "entry_snr",
                  "time_stop_count", "trail_armed", "nn_rank", "nn_score", "industry", "last", "price_src"):
            self.assertIn(k, p)
        self.assertEqual(p["industry"], "ETF")


class TestLegacy(ComboTestBase):
    def test_legacy_0050_excluded_after_cutover(self):
        st = {"baseline": {"legacy_positions": {"0050": 4000}, "start_date": "2026-11-03"}}
        (self.paper / "sim_state.json").write_text(json.dumps(st), encoding="utf-8")
        a = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        a["combo_since"] = "2026-11-18"
        (self.paper / "account.json").write_text(json.dumps(a), encoding="utf-8")
        with patch.object(self.sim_trader, "login") as mlogin:
            api = MagicMock()
            mlogin.return_value = api
            pos_mock = MagicMock()
            pos_mock.code = "0050"
            pos_mock.quantity = 1000
            pos_mock.price = 100.0
            pos_mock.last_price = 101.0
            pos_mock.pnl = 1000.0
            api.list_positions.return_value = [pos_mock]
            api.account_balance.return_value = MagicMock(acc_balance=1000000)
            api.list_trades.return_value = []
            api.list_profit_loss.return_value = []
            self.sim_trader.snapshot()
        snap = json.loads((self.paper / "sim_snapshot.json").read_text(encoding="utf-8"))
        self.assertNotIn("0050", snap["legacy_codes"])
        self.assertTrue(any(p["code"] == "0050" for p in snap["positions"]))
        # 0050 in strategy sleeve
        self.assertIn("sleeve", snap)
        st2 = json.loads((self.paper / "sim_state.json").read_text(encoding="utf-8"))
        self.assertEqual(st2["baseline"]["legacy_positions"]["0050"], 4000)

    def test_a1_off_sell_not_legacy(self):
        rows = [{"code": "2330", "weight": 1.0, "close": 100.0, "rank": 1, "score": 1.0, "industry": "SEMI"}]
        held = {"0050": 1000}
        px = {"0050": {"close": 100.0, "bid": 99.5}, "2330": {"close": 100.0}}
        orders, _ = self.sim_trader.plan(rows, held, px, a1_signal="off")
        a1_orders = [o for o in orders if o["code"] == "0050"]
        self.assertTrue(a1_orders)
        self.assertFalse(any(o.get("legacy") for o in a1_orders))


class TestBackupLocation(ComboTestBase):
    def test_backup_outside_paper_nn(self):
        rows = [{"code": "2330", "weight": 1.0, "close": 1000.0, "rank": 1, "score": 1.0, "industry": "SEMI"}]
        self._write_target("2026-12", rows)
        with patch.object(self.nn_paper, "fetch_closes", return_value={"2330": (1000.0, "test")}):
            self.nn_paper.daily()
        self.assertFalse(any(self.paper.rglob("backup_pre_combo_*")))
        self.assertTrue(any(self.backup.glob("backup_pre_combo_*")))


class TestSimTargets(ComboTestBase):
    def test_a1_on_shares_and_nn3_budget(self):
        with patch.object(self.sim_trader, "_switched", return_value=True):
            px = {"2330": {"close": 100.0}, "0050": {"close": 100.0}}
            rows = [{"code": "2330", "weight": 1.0, "close": 100.0}]
            tgt = self.sim_trader.target_shares(rows, px, a1_signal="on")
            self.assertEqual(tgt["0050"], int(980000 * 0.4 // 100))
            self.assertEqual(tgt["2330"], int(1.0 * 980000 * 0.6 // 100))


class TestSafePlaceOnly(ComboTestBase):
    def test_place_only_via_safe_place_sim_true(self):
        with patch.object(self.sim_trader, "login") as mlogin, \
             patch.object(self.sim_trader, "safe_place") as mplace, \
             patch.object(self.sim_trader, "make_order", return_value=MagicMock()), \
             patch.object(self.sim_trader, "positions", return_value={}), \
             patch.object(self.sim_trader, "snap_prices", return_value={"2330": {"close": 100.0}}), \
             patch.object(self.sim_trader, "latest_target", return_value=("2026-12", [{"code": "2330", "weight": 1.0, "close": 100.0}])):
            api = MagicMock()
            api.Contracts.Stocks.__getitem__.return_value = MagicMock(code="2330")
            mlogin.return_value = api
            mplace.return_value = MagicMock(order=MagicMock(id="x"), status=MagicMock(status="OK", msg=""))
            self.sim_trader.run(True, "open")
            self.assertTrue(mplace.called)
            self.assertTrue(self.sim_trader.SIMULATION_ONLY)


class TestAC10OnlyA1(ComboTestBase):
    def test_non_first_second_day_only_a1(self):
        # mark switched
        a = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        a["combo_since"] = "2026-11-01"
        (self.paper / "account.json").write_text(json.dumps(a), encoding="utf-8")
        # fixed dates
        fixed = date(2026, 11, 18)
        prev = (fixed - timedelta(days=1)).isoformat()
        sig = {"date": prev, "close": 25000, "ma200": 24000, "signal": "on", "source": "test", "stale": False}
        (self.paper / "a1_signal.json").write_text(json.dumps(sig), encoding="utf-8")
        self._write_target("2026-11", [{"code": "2330", "weight": 1.0, "close": 100.0, "rank": 1, "score": 1.0, "industry": "SEMI"}])
        with patch.object(self.sim_trader, "_today", return_value=fixed), \
             patch.object(self.sim_trader, "nth_trading_day_of_month", return_value=5), \
             patch.object(self.sim_trader, "login") as mlogin, \
             patch.object(self.sim_trader, "safe_place") as mplace, \
             patch.object(self.sim_trader, "make_order", return_value=MagicMock()), \
             patch.object(self.sim_trader, "positions", return_value={"2330": 100, "0050": 0}), \
             patch.object(self.sim_trader, "snap_prices", return_value={"2330": {"close": 100.0}, "0050": {"close": 100.0}}), \
             patch.object(self.sim_trader, "latest_target", return_value=("2026-11", [{"code": "2330", "weight": 1.0, "close": 100.0}])):
            api = MagicMock()
            def _stock(code):
                m = MagicMock()
                m.code = code
                return m
            api.Contracts.Stocks.__getitem__.side_effect = _stock
            mlogin.return_value = api
            mplace.return_value = MagicMock(order=MagicMock(id="x"), status=MagicMock(status="OK", msg=""))
            self.sim_trader.auto("open", False)
            self.assertTrue(mplace.called)
            placed_codes = []
            for call in mplace.call_args_list:
                contract = call.args[1]
                placed_codes.append(contract.code)
            self.assertEqual(set(placed_codes), {"0050"})

    def test_same_day_no_duplicate_a1(self):
        a = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        a["combo_since"] = "2026-11-01"
        (self.paper / "account.json").write_text(json.dumps(a), encoding="utf-8")
        fixed = date(2026, 11, 18)
        st = {"2026-11": {"a1_last_day": fixed.isoformat()}}
        (self.paper / "sim_state.json").write_text(json.dumps(st), encoding="utf-8")
        self._write_target("2026-11", [{"code": "2330", "weight": 1.0, "close": 100.0, "rank": 1, "score": 1.0, "industry": "SEMI"}])
        prev = (fixed - timedelta(days=1)).isoformat()
        sig = {"date": prev, "close": 25000, "ma200": 24000, "signal": "on", "source": "test", "stale": False}
        (self.paper / "a1_signal.json").write_text(json.dumps(sig), encoding="utf-8")
        with patch.object(self.sim_trader, "_today", return_value=fixed), \
             patch.object(self.sim_trader, "nth_trading_day_of_month", return_value=5), \
             patch.object(self.sim_trader, "login") as mlogin, \
             patch.object(self.sim_trader, "safe_place") as mplace, \
             patch.object(self.sim_trader, "latest_target", return_value=("2026-11", [{"code": "2330", "weight": 1.0, "close": 100.0}])):
            self.sim_trader.auto("open", False)
            self.assertFalse(mplace.called)


class TestAC2StaleNoSell(ComboTestBase):
    def test_stale_keeps_0050(self):
        with patch.object(self.sim_trader, "_switched", return_value=True):
            rows = [{"code": "2330", "weight": 1.0, "close": 100.0}]
            held = {"0050": 500}
            px = {"0050": {"close": 100.0}, "2330": {"close": 100.0}}
            tgt = self.sim_trader.target_shares(rows, px, a1_signal=None, held=held, stale=True)
            self.assertEqual(tgt["0050"], 500)
            orders, _ = self.sim_trader.plan(rows, held, px, a1_signal=None, stale=True)
            self.assertFalse(any(o["code"] == "0050" and o["side"] == "Sell" for o in orders))


class TestAC1Cta(ComboTestBase):
    def test_stale_exit_zero_keeps_prior(self):
        prev = {"date": "2026-11-17", "close": 25000, "ma200": 24000, "signal": "on", "source": "ok", "stale": False}
        (self.paper / "a1_signal.json").write_text(json.dumps(prev), encoding="utf-8")
        (self.paper / "a1_signals.csv").write_text("date,close,ma200,signal,source,stale\n2026-11-17,25000,24000,on,ok,False\n", encoding="utf-8")
        fixed = date(2026, 11, 18)
        with patch.object(self.cta_a1, "_today", return_value=fixed), \
             patch.object(self.cta_a1.data, "get_price", return_value=None), \
             patch.object(self.cta_a1.quotes, "get_feed", return_value=MagicMock(session_bar=lambda x: None)):
            rc = self.cta_a1.update()
        self.assertEqual(rc, 0)
        # prior non-stale still in csv
        csv_text = (self.paper / "a1_signals.csv").read_text(encoding="utf-8")
        self.assertIn("2026-11-17", csv_text)
        self.assertIn("on", csv_text)
        # today row is stale
        self.assertIn(fixed.isoformat(), csv_text)
        self.assertIn("True", csv_text)  # stale

    def test_enough_history_writes_on(self):
        import pandas as pd
        import numpy as np
        fixed = date(2026, 11, 18)
        # 遞增收盤，最後一天明顯高於 200 日均線
        idx = pd.bdate_range(end=fixed, periods=250)
        closes = np.linspace(20000.0, 26000.0, 250)
        df = pd.DataFrame({"Open": 100, "High": 101, "Low": 99, "Close": closes, "Volume": 1}, index=idx)
        with patch.object(self.cta_a1, "_today", return_value=fixed), \
             patch.object(self.cta_a1.data, "get_price", return_value=df), \
             patch.object(self.cta_a1.quotes, "get_feed", return_value=MagicMock(session_bar=lambda x: None)):
            rc = self.cta_a1.update()
        self.assertEqual(rc, 0)
        rec = json.loads((self.paper / "a1_signal.json").read_text(encoding="utf-8"))
        self.assertFalse(rec["stale"])
        self.assertEqual(rec["signal"], "on")
        self.assertEqual(rec["date"], fixed.isoformat())
        self.assertEqual(rec["close"], closes[-1])
        expected_ma = float(closes[-200:].mean())
        self.assertAlmostEqual(rec["ma200"], expected_ma, places=2)
        self.assertGreater(rec["close"], rec["ma200"])

    def test_enough_history_writes_off(self):
        import pandas as pd
        import numpy as np
        fixed = date(2026, 11, 18)
        # 遞減收盤，最後一天明顯低於 200 日均線
        idx = pd.bdate_range(end=fixed, periods=250)
        closes = np.linspace(26000.0, 20000.0, 250)
        df = pd.DataFrame({"Open": 100, "High": 101, "Low": 99, "Close": closes, "Volume": 1}, index=idx)
        with patch.object(self.cta_a1, "_today", return_value=fixed), \
             patch.object(self.cta_a1.data, "get_price", return_value=df), \
             patch.object(self.cta_a1.quotes, "get_feed", return_value=MagicMock(session_bar=lambda x: None)):
            rc = self.cta_a1.update()
        self.assertEqual(rc, 0)
        rec = json.loads((self.paper / "a1_signal.json").read_text(encoding="utf-8"))
        self.assertFalse(rec["stale"])
        self.assertEqual(rec["signal"], "off")
        self.assertEqual(rec["date"], fixed.isoformat())
        self.assertEqual(rec["close"], closes[-1])
        expected_ma = float(closes[-200:].mean())
        self.assertAlmostEqual(rec["ma200"], expected_ma, places=2)
        self.assertLess(rec["close"], rec["ma200"])


class TestNoOpenNoFill(ComboTestBase):
    def test_no_open_no_a1_buy(self):
        a = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        a["combo_since"] = "2026-11-18"
        a["a1"] = {"target_ntd": 400000, "cash": 400000, "shares": 0, "state": "cash"}
        (self.paper / "account.json").write_text(json.dumps(a), encoding="utf-8")
        sig = {"date": "2026-11-17", "signal": "on", "stale": False}
        (self.paper / "a1_signal.json").write_text(json.dumps(sig), encoding="utf-8")
        fixed = date(2026, 11, 18)
        with patch.object(self.nn_paper, "_today", return_value=fixed), \
             patch.object(self.nn_paper, "fetch_open", return_value=None), \
             patch.object(self.nn_paper, "fetch_closes", return_value={}), \
             patch.object(self.nn_paper.tw_calendar, "is_trading_day", return_value=True):
            self.nn_paper.daily()
        a2 = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        self.assertEqual(a2["a1"]["shares"], 0)
        ledger = (self.paper / "ledger.csv").read_text(encoding="utf-8")
        self.assertNotIn("a1_on", ledger)


# ---------- New required tests (必要 2) ----------

class TestCutoverSplit(ComboTestBase):
    def test_cutover_60_40_split(self):
        """(a) 切換時 60/40 切分，不 patch _equity。"""
        rows = [{"code": "2330", "weight": 1.0, "close": 1000.0, "rank": 1, "score": 1.0, "industry": "SEMI"}]
        self._write_target("2026-12", rows)
        fixed = date(2026, 11, 18)
        with patch.object(self.nn_paper, "_today", return_value=fixed), \
             patch.object(self.nn_paper, "fetch_closes", return_value={"2330": (1000.0, "test")}):
            self.nn_paper.daily()
        a = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        self.assertIn("combo_since", a)
        eq = a["equity"]
        self.assertAlmostEqual(a["a1"]["target_ntd"], eq * 0.4, delta=eq * 0.01)
        self.assertAlmostEqual(a["a1"]["cash"], eq * 0.4, delta=eq * 0.01)
        nn_mv = sum(p["shares"] * p.get("last", p["avg_price"]) for p in a["positions"] if p["ticker"] != "0050")
        nn_cash = a["cash"] - a["a1"]["cash"]
        self.assertAlmostEqual(nn_mv + nn_cash, eq * 0.6, delta=eq * 0.01)
        ledger = (self.paper / "ledger.csv").read_text(encoding="utf-8")
        self.assertIn("combo_cutover", ledger)


class TestMonthlyRebalance(ComboTestBase):
    def test_rebalance_nn3_up_a1_holds(self):
        """(b) NN3 先漲 +50%，再平衡後約 60/40，A1 持有 0050。"""
        # start switched, NN3 holding, A1 holding
        a = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        a["combo_since"] = "2026-11-01"
        a["strategy"] = "nn3_60_a1_40"
        a["last_target"] = "2026-11"
        a["cash"] = 600_000
        a["a1"] = {"target_ntd": 400_000, "cash": 100_000, "shares": 3000, "state": "holding"}
        a["positions"] = [
            {"ticker": "2330", "name": "TSMC", "shares": 500, "avg_price": 1000, "last": 1000,
             "entry_date": "2026-11-01", "entry_snr": None, "time_stop_count": 0, "trail_armed": False,
             "nn_rank": 1, "nn_score": 1, "industry": "SEMI"},
            {"ticker": "0050", "name": "元大台灣50", "shares": 3000, "avg_price": 100, "last": 100,
             "entry_date": "2026-11-01", "entry_snr": None, "time_stop_count": 0, "trail_armed": False,
             "nn_rank": None, "nn_score": None, "industry": "ETF"},
        ]
        # equity ≈ 600k cash + 500*1000 + 3000*100 = 600k + 500k + 300k = 1.4M
        a["equity"] = 1_400_000
        (self.paper / "account.json").write_text(json.dumps(a), encoding="utf-8")
        # new month target, prices: 2330 +50% = 1500
        rows = [{"code": "2330", "weight": 1.0, "close": 1500.0, "rank": 1, "score": 1.0, "industry": "SEMI"}]
        self._write_target("2026-12", rows)
        fixed = date(2026, 12, 1)
        with patch.object(self.nn_paper, "_today", return_value=fixed), \
             patch.object(self.nn_paper, "fetch_closes", return_value={"2330": (1500.0, "test"), "0050": (100.0, "test")}):
            self.nn_paper.daily()
        a2 = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        eq = a2["equity"]
        a1_side = a2["a1"]["cash"] + sum(p["shares"] * p.get("last", 100) for p in a2["positions"] if p["ticker"] == "0050")
        nn_side = sum(p["shares"] * p.get("last", 1500) for p in a2["positions"] if p["ticker"] != "0050") + (a2["cash"] - a2["a1"]["cash"])
        self.assertAlmostEqual(nn_side / eq, 0.60, delta=0.01)
        self.assertAlmostEqual(a1_side / eq, 0.40, delta=0.01)
        self.assertGreaterEqual(a2["a1"]["cash"], 0)
        self.assertLessEqual(a2["a1"]["cash"], a2["cash"])

    def test_rebalance_nn3_down_a1_cash(self):
        """(b) NN3 先跌 −30%，再平衡後約 60/40，A1 持現金。"""
        a = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        a["combo_since"] = "2026-11-01"
        a["strategy"] = "nn3_60_a1_40"
        a["last_target"] = "2026-11"
        a["cash"] = 700_000
        a["a1"] = {"target_ntd": 400_000, "cash": 400_000, "shares": 0, "state": "cash"}
        a["positions"] = [
            {"ticker": "2330", "name": "TSMC", "shares": 300, "avg_price": 1000, "last": 700,
             "entry_date": "2026-11-01", "entry_snr": None, "time_stop_count": 0, "trail_armed": False,
             "nn_rank": 1, "nn_score": 1, "industry": "SEMI"},
        ]
        a["equity"] = 1_000_000  # approx
        (self.paper / "account.json").write_text(json.dumps(a), encoding="utf-8")
        rows = [{"code": "2330", "weight": 1.0, "close": 700.0, "rank": 1, "score": 1.0, "industry": "SEMI"}]
        self._write_target("2026-12", rows)
        fixed = date(2026, 12, 1)
        with patch.object(self.nn_paper, "_today", return_value=fixed), \
             patch.object(self.nn_paper, "fetch_closes", return_value={"2330": (700.0, "test")}):
            self.nn_paper.daily()
        a2 = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        eq = a2["equity"]
        a1_side = a2["a1"]["cash"]
        nn_side = sum(p["shares"] * p.get("last", 700) for p in a2["positions"] if p["ticker"] != "0050") + (a2["cash"] - a2["a1"]["cash"])
        self.assertAlmostEqual(nn_side / eq, 0.60, delta=0.015)
        self.assertAlmostEqual(a1_side / eq, 0.40, delta=0.015)
        self.assertGreaterEqual(a2["a1"]["cash"], 0)
        self.assertLessEqual(a2["a1"]["cash"], a2["cash"])

    def test_rebalance_a1_topup_with_fee(self):
        """必要 2：A1 加碼要算進手續費，且會加碼。"""
        a = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        a["combo_since"] = "2026-11-01"
        a["strategy"] = "nn3_60_a1_40"
        a["last_target"] = "2026-11"
        a["cash"] = 700_000
        a["a1"] = {"target_ntd": 400_000, "cash": 300_000, "shares": 1000, "state": "holding"}
        a["positions"] = [
            {"ticker": "2330", "name": "TSMC", "shares": 300, "avg_price": 1000, "last": 1000,
             "entry_date": "2026-11-01", "entry_snr": None, "time_stop_count": 0, "trail_armed": False,
             "nn_rank": 1, "nn_score": 1, "industry": "SEMI"},
            {"ticker": "0050", "name": "元大台灣50", "shares": 1000, "avg_price": 100, "last": 100,
             "entry_date": "2026-11-01", "entry_snr": None, "time_stop_count": 0, "trail_armed": False,
             "nn_rank": None, "nn_score": None, "industry": "ETF"},
        ]
        a["equity"] = 1_100_000
        (self.paper / "account.json").write_text(json.dumps(a), encoding="utf-8")
        rows = [{"code": "2330", "weight": 1.0, "close": 1000.0, "rank": 1, "score": 1.0, "industry": "SEMI"}]
        self._write_target("2026-12", rows)
        fixed = date(2026, 12, 1)
        with patch.object(self.nn_paper, "_today", return_value=fixed), \
             patch.object(self.nn_paper, "fetch_closes", return_value={"2330": (1000.0, "test"), "0050": (100.0, "test")}):
            self.nn_paper.daily()
        a2 = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        a1_shares = next(p["shares"] for p in a2["positions"] if p["ticker"] == "0050")
        self.assertGreater(a1_shares, 1000)  # 有加碼
        eq = a2["equity"]
        a1_side = a2["a1"]["cash"] + a1_shares * 100.0
        self.assertAlmostEqual(a1_side / eq, 0.40, delta=0.02)
        # NN3 沒用到 A1 現金
        self.assertGreaterEqual(a2["a1"]["cash"], 0)
        self.assertLessEqual(a2["a1"]["cash"], a2["cash"])


class TestPositionNextDay(ComboTestBase):
    def test_position_changes_next_day(self):
        """(c) 部位在 t+1 才變動：d-1 on 訊號，d 開盤價成交。"""
        a = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        a["combo_since"] = "2026-11-01"
        a["a1"] = {"target_ntd": 400_000, "cash": 400_000, "shares": 0, "state": "cash"}
        a["cash"] = 1_000_000
        (self.paper / "account.json").write_text(json.dumps(a), encoding="utf-8")
        sig = {"date": "2026-11-16", "close": 25000, "ma200": 24000, "signal": "on", "source": "test", "stale": False}
        (self.paper / "a1_signal.json").write_text(json.dumps(sig), encoding="utf-8")
        fixed = date(2026, 11, 17)
        open_px = 100.0
        with patch.object(self.nn_paper, "_today", return_value=fixed), \
             patch.object(self.nn_paper, "fetch_open", return_value=open_px), \
             patch.object(self.nn_paper, "fetch_closes", return_value={}), \
             patch.object(self.nn_paper.tw_calendar, "is_trading_day", side_effect=lambda d: d.weekday() < 5):
            self.nn_paper.daily()
        a2 = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        self.assertGreater(a2["a1"]["shares"], 0)
        ledger = (self.paper / "ledger.csv").read_text(encoding="utf-8")
        self.assertIn("a1_on", ledger)
        # fill price = open * 1.001
        self.assertIn(str(round(open_px * 1.001, 4)), ledger)

    def test_same_day_signal_no_position_change(self):
        """(c) 訊號日期 = d 時部位不變。"""
        a = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        a["combo_since"] = "2026-11-01"
        a["a1"] = {"target_ntd": 400_000, "cash": 400_000, "shares": 0, "state": "cash"}
        (self.paper / "account.json").write_text(json.dumps(a), encoding="utf-8")
        sig = {"date": "2026-11-17", "signal": "on", "stale": False}
        (self.paper / "a1_signal.json").write_text(json.dumps(sig), encoding="utf-8")
        fixed = date(2026, 11, 17)
        with patch.object(self.nn_paper, "_today", return_value=fixed), \
             patch.object(self.nn_paper, "fetch_open", return_value=100.0), \
             patch.object(self.nn_paper, "fetch_closes", return_value={}), \
             patch.object(self.nn_paper.tw_calendar, "is_trading_day", return_value=True):
            self.nn_paper.daily()
        a2 = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        self.assertEqual(a2["a1"]["shares"], 0)


class TestSellTaxPath(ComboTestBase):
    def test_a1_off_sell_tax_via_nn_paper(self):
        """(d) 0050 賣出稅走 nn_paper 路徑。"""
        a = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        a["combo_since"] = "2026-11-01"
        a["cash"] = 600_000
        a["a1"] = {"target_ntd": 400_000, "cash": 0, "shares": 1000, "state": "holding"}
        a["positions"] = [{
            "ticker": "0050", "name": "元大台灣50", "shares": 1000, "avg_price": 100.0,
            "entry_date": "2026-11-01", "entry_snr": None, "time_stop_count": 0, "trail_armed": False,
            "nn_rank": None, "nn_score": None, "industry": "ETF", "last": 100.0, "price_src": "test"
        }]
        a["equity"] = 700_000
        (self.paper / "account.json").write_text(json.dumps(a), encoding="utf-8")
        sig = {"date": "2026-11-16", "signal": "off", "stale": False}
        (self.paper / "a1_signal.json").write_text(json.dumps(sig), encoding="utf-8")
        fixed = date(2026, 11, 17)
        open_px = 100.0
        cash_before = a["cash"]
        a1_cash_before = a["a1"]["cash"]
        with patch.object(self.nn_paper, "_today", return_value=fixed), \
             patch.object(self.nn_paper, "fetch_open", return_value=open_px), \
             patch.object(self.nn_paper, "fetch_closes", return_value={}), \
             patch.object(self.nn_paper.tw_calendar, "is_trading_day", side_effect=lambda d: d.weekday() < 5):
            self.nn_paper.daily()
        a2 = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        fill_price = open_px * 0.999
        notional = 1000 * fill_price
        expected_delta = notional - max(20.0, notional * 0.001425) - notional * 0.003
        self.assertAlmostEqual(a2["cash"] - cash_before, expected_delta, places=1)
        self.assertAlmostEqual(a2["a1"]["cash"] - a1_cash_before, expected_delta, places=1)


class TestSimulationBehavior(ComboTestBase):
    def test_login_simulation_true_and_safe_place_guard(self):
        """(e) simulation=True 實際行為 + LiveTradingRefused。"""
        import types
        fake_sj = MagicMock()
        api_mock = MagicMock()
        fake_sj.Shioaji = MagicMock(return_value=api_mock)
        fake_quotes = types.ModuleType("quotes")
        fake_quotes._simulation_forced = MagicMock(return_value=True)
        fake_quotes._shioaji_keys = MagicMock(return_value=("fake_key", "fake_secret"))
        with patch.dict(sys.modules, {"shioaji": fake_sj, "quotes": fake_quotes}):
            api = self.sim_trader.login()
            self.assertTrue(fake_sj.Shioaji.called)
            args, kwargs = fake_sj.Shioaji.call_args
            self.assertEqual(kwargs.get("simulation"), True)
            api_mock.login.assert_called()
            api_mock.activate_ca.assert_not_called()
            # safe_place with the login-created object
            c, o = MagicMock(), MagicMock()
            self.sim_trader.safe_place(api, c, o)
            api_mock.place_order.assert_called_once()
        # safe_place with wrong object
        with self.assertRaises(self.sim_trader.LiveTradingRefused):
            self.sim_trader.safe_place(MagicMock(), MagicMock(), MagicMock())
        # _simulation_forced False refuses (still under fake modules)
        fake_quotes2 = types.ModuleType("quotes")
        fake_quotes2._simulation_forced = MagicMock(return_value=False)
        fake_quotes2._shioaji_keys = MagicMock(return_value=("k", "s"))
        with patch.dict(sys.modules, {"shioaji": fake_sj, "quotes": fake_quotes2}):
            with self.assertRaises(self.sim_trader.LiveTradingRefused):
                self.sim_trader.login()


class TestFetchOpenTimestamp(ComboTestBase):
    def test_fetch_open_requires_matching_date(self):
        """可選 A：3 種情況。"""
        import sys
        import types
        import pandas as pd

        # (1) 沒有時間戳、後備也沒有 → None
        q1 = MagicMock()
        q1.open = 100.0
        q1.ts = None
        feed1 = MagicMock()
        feed1.last.return_value = q1
        fake_data1 = MagicMock()
        fake_data1.get_price.return_value = None
        with patch.object(self.nn_paper, "quotes", MagicMock(get_feed=lambda: feed1)), \
             patch.dict(sys.modules, {"data": fake_data1}):
            result = self.nn_paper.fetch_open("0050", "2026-11-17")
            self.assertIsNone(result)

        # (2) 時間戳日期不符 → 不採用報價，改用後備 Open
        q2 = MagicMock()
        q2.open = 99.0
        q2.ts = "2026-11-16 09:00"
        feed2 = MagicMock()
        feed2.last.return_value = q2
        day = "2026-11-17"
        df = pd.DataFrame({"Open": [101.5], "High": [102], "Low": [100], "Close": [101], "Volume": [1]},
                          index=pd.DatetimeIndex([pd.Timestamp(day)]))
        fake_data2 = MagicMock()
        fake_data2.get_price.return_value = df
        with patch.object(self.nn_paper, "quotes", MagicMock(get_feed=lambda: feed2)), \
             patch.dict(sys.modules, {"data": fake_data2}):
            result = self.nn_paper.fetch_open("0050", day)
            self.assertEqual(result, 101.5)

        # (3) 時間戳日期 = day → 回傳報價 open
        q3 = MagicMock()
        q3.open = 102.5
        q3.ts = "2026-11-17 09:00"
        feed3 = MagicMock()
        feed3.last.return_value = q3
        with patch.object(self.nn_paper, "quotes", MagicMock(get_feed=lambda: feed3)):
            result = self.nn_paper.fetch_open("0050", "2026-11-17")
            self.assertEqual(result, 102.5)


if __name__ == "__main__":
    unittest.main()
