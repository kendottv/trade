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
        # signal for today (assume today is not 1st/2nd)
        today = date.today().isoformat()
        prev = (date.today() - timedelta(days=1)).isoformat()
        sig = {"date": prev, "close": 25000, "ma200": 24000, "signal": "on", "source": "test", "stale": False}
        (self.paper / "a1_signal.json").write_text(json.dumps(sig), encoding="utf-8")
        self._write_target("2026-11", [{"code": "2330", "weight": 1.0, "close": 100.0, "rank": 1, "score": 1.0, "industry": "SEMI"}])
        with patch.object(self.sim_trader, "nth_trading_day_of_month", return_value=5), \
             patch.object(self.sim_trader, "login") as mlogin, \
             patch.object(self.sim_trader, "safe_place") as mplace, \
             patch.object(self.sim_trader, "make_order", return_value=MagicMock()), \
             patch.object(self.sim_trader, "positions", return_value={"2330": 100, "0050": 0}), \
             patch.object(self.sim_trader, "snap_prices", return_value={"2330": {"close": 100.0}, "0050": {"close": 100.0}}), \
             patch.object(self.sim_trader, "latest_target", return_value=("2026-11", [{"code": "2330", "weight": 1.0, "close": 100.0}])):
            api = MagicMock()
            # make Contracts.Stocks[code] return object with correct .code
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
        st = {"2026-11": {"a1_last_day": date.today().isoformat()}}
        (self.paper / "sim_state.json").write_text(json.dumps(st), encoding="utf-8")
        self._write_target("2026-11", [{"code": "2330", "weight": 1.0, "close": 100.0, "rank": 1, "score": 1.0, "industry": "SEMI"}])
        prev = (date.today() - timedelta(days=1)).isoformat()
        sig = {"date": prev, "close": 25000, "ma200": 24000, "signal": "on", "source": "test", "stale": False}
        (self.paper / "a1_signal.json").write_text(json.dumps(sig), encoding="utf-8")
        with patch.object(self.sim_trader, "nth_trading_day_of_month", return_value=5), \
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
        with patch.object(self.cta_a1.data, "get_price", return_value=None), \
             patch.object(self.cta_a1.quotes, "get_feed", return_value=MagicMock(session_bar=lambda x: None)):
            rc = self.cta_a1.update()
        self.assertEqual(rc, 0)
        # prior non-stale still in csv
        csv_text = (self.paper / "a1_signals.csv").read_text(encoding="utf-8")
        self.assertIn("2026-11-17", csv_text)
        self.assertIn("on", csv_text)
        # today row is stale
        today = date.today().isoformat()
        self.assertIn(today, csv_text)
        self.assertIn("True", csv_text)  # stale

    def test_enough_history_writes_on(self):
        import pandas as pd
        today = date.today()
        # build 250 business days ending today
        idx = pd.bdate_range(end=today, periods=250)
        df = pd.DataFrame({"Open": 100, "High": 101, "Low": 99, "Close": 25000.0, "Volume": 1}, index=idx)
        with patch.object(self.cta_a1.data, "get_price", return_value=df), \
             patch.object(self.cta_a1.quotes, "get_feed", return_value=MagicMock(session_bar=lambda x: None)):
            rc = self.cta_a1.update()
        self.assertEqual(rc, 0)
        rec = json.loads((self.paper / "a1_signal.json").read_text(encoding="utf-8"))
        self.assertFalse(rec["stale"])
        self.assertIn(rec["signal"], ("on", "off"))


class TestNoOpenNoFill(ComboTestBase):
    def test_no_open_no_a1_buy(self):
        a = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        a["combo_since"] = "2026-11-18"
        a["a1"] = {"target_ntd": 400000, "cash": 400000, "shares": 0, "state": "cash"}
        (self.paper / "account.json").write_text(json.dumps(a), encoding="utf-8")
        sig = {"date": "2026-11-17", "signal": "on", "stale": False}
        (self.paper / "a1_signal.json").write_text(json.dumps(sig), encoding="utf-8")
        with patch.object(self.nn_paper, "fetch_open", return_value=None), \
             patch.object(self.nn_paper, "fetch_closes", return_value={}), \
             patch.object(self.nn_paper.tw_calendar, "is_trading_day", return_value=True):
            self.nn_paper.daily()
        a2 = json.loads((self.paper / "account.json").read_text(encoding="utf-8"))
        self.assertEqual(a2["a1"]["shares"], 0)
        ledger = (self.paper / "ledger.csv").read_text(encoding="utf-8")
        self.assertNotIn("a1_on", ledger)


if __name__ == "__main__":
    unittest.main()
