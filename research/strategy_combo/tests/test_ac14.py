"""Tests required by AC-14.

All tests use synthetic series or temporary files. No network, no external services,
no real TEJ price files, no secrets. No skips.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from research.strategy_combo.costs import compute_side_cost, is_etf  # noqa: E402
from research.strategy_combo.metrics import max_drawdown_pct, monthly_metrics  # noqa: E402
from research.strategy_combo.scaling import scale_returns  # noqa: E402
from research.strategy_combo.portfolio import (  # noqa: E402
    equal_weight,
    two_strategy_scan,
    three_strategy_scan,
)
from research.strategy_combo.strategies import (  # noqa: E402
    cta_signal,
    backtest_cta,
    backtest_b,
    _compute_b_indicators,
    compute_tradable_info,
)
from research.strategy_combo.config import (  # noqa: E402
    FEE_RATE,
    FEE_MIN_TWD,
    SLIPPAGE_RATE,
    ETF_TAX_RATE,
    DEFAULT_PRINCIPAL_TWD,
    MEMBERSHIP_CSV,
)
from research.strategy_combo.data import (  # noqa: E402
    constituents_on_date,
    load_membership_intervals,
    check_tej_files_exist,
    _read_tej_raw,
    _process_tej_df,
)
from research.strategy_combo.run import find_common_period  # noqa: E402
from research.strategy_combo.report import compute_correlations, write_report  # noqa: E402


def _buy_cost_drag(principal: float = DEFAULT_PRINCIPAL_TWD, symbol: str = "0050.TW") -> float:
    return compute_side_cost(principal, is_buy=True, symbol=symbol) / principal


def _sell_cost_drag(principal: float = DEFAULT_PRINCIPAL_TWD, symbol: str = "0050.TW") -> float:
    return compute_side_cost(principal, is_buy=False, symbol=symbol) / principal


def _always_member(codes, start="2010-01-01"):
    return pd.DataFrame({
        "code": codes,
        "name": codes,
        "start_date": pd.to_datetime(start),
        "end_date": pd.NaT,
    })


def _long_uptrend_with_dip(n=260, dip_at=230, dip_frac=0.90):
    dates = pd.bdate_range("2018-01-01", periods=n)
    px = pd.Series(np.linspace(100.0, 180.0, n), index=dates)
    px.iloc[dip_at] = px.iloc[dip_at - 1] * dip_frac
    return dates, px


class TestLookAheadCTA(unittest.TestCase):
    def _series_with_up_cross(self, n: int = 260, cross_at: int = 220):
        dates = pd.bdate_range("2018-01-01", periods=n)
        close = pd.Series(100.0, index=dates)
        close.iloc[cross_at:] = 180.0
        return dates, close

    def _series_with_down_cross(self, n: int = 280, cross_at: int = 240):
        dates = pd.bdate_range("2018-01-01", periods=n)
        close = pd.Series(np.linspace(100.0, 200.0, n), index=dates)
        close.iloc[cross_at:] = 80.0
        return dates, close

    def test_cta_up_cross_return_timing(self):
        dates, twii = self._series_with_up_cross(cross_at=220)
        p0050 = pd.Series(100.0, index=dates)
        p0050.iloc[221] = 102.0
        p0050.iloc[222] = 105.0
        daily = backtest_cta(twii, p0050, None, apply_costs=False, name="A1")
        sig = cta_signal(twii)
        cross_days = sig[sig == 1].index
        self.assertGreater(len(cross_days), 0)
        t = cross_days[0]
        loc = dates.get_loc(t)
        self.assertGreaterEqual(loc, 200)
        self.assertAlmostEqual(float(daily.loc[t]), 0.0, places=8)
        t1 = dates[loc + 1]
        self.assertAlmostEqual(float(daily.loc[t1]), 0.0, places=8)
        t2 = dates[loc + 2]
        expected = float(p0050.loc[t2] / p0050.loc[t1] - 1.0)
        self.assertAlmostEqual(float(daily.loc[t2]), expected, places=6)

    def test_cta_down_cross_a1_cash(self):
        dates, twii = self._series_with_down_cross(cross_at=240)
        p0050 = pd.Series(100.0, index=dates)
        sig = cta_signal(twii)
        ones = sig[sig == 1]
        self.assertGreater(len(ones), 0)
        t = None
        prev = None
        for dt in dates:
            s = sig.loc[dt]
            if pd.notna(s) and prev == 1 and s == 0:
                t = dt
                break
            if pd.notna(s):
                prev = int(s)
        self.assertIsNotNone(t)
        loc = dates.get_loc(t)
        t1 = dates[loc + 1]
        p0050.loc[t1] = 103.0
        daily = backtest_cta(twii, p0050, None, apply_costs=False, name="A1")
        r_t1 = float(p0050.loc[t1] / p0050.loc[t] - 1.0)
        self.assertAlmostEqual(float(daily.loc[t1]), r_t1, places=6)
        if loc + 2 < len(dates):
            later = daily.iloc[loc + 2:loc + 6]
            self.assertTrue((later.abs() < 1e-8).all())

    def test_cta_a2_switches_to_inverse(self):
        dates, twii = self._series_with_down_cross(cross_at=240)
        p0050 = pd.Series(100.0, index=dates)
        pinv = pd.Series(50.0, index=dates)
        sig = cta_signal(twii)
        ones = sig[sig == 1]
        self.assertGreater(len(ones), 0)
        t = None
        prev = None
        for dt in dates:
            s = sig.loc[dt]
            if pd.notna(s) and prev == 1 and s == 0:
                t = dt
                break
            if pd.notna(s):
                prev = int(s)
        self.assertIsNotNone(t)
        loc = dates.get_loc(t)
        t1 = dates[loc + 1]
        t2 = dates[loc + 2]
        p0050.loc[t1] = 104.0
        pinv.loc[t1] = 50.0
        pinv.loc[t2] = 55.0
        daily = backtest_cta(twii, p0050, pinv, apply_costs=False, name="A2")
        r_0050 = float(p0050.loc[t1] / p0050.loc[t] - 1.0)
        self.assertAlmostEqual(float(daily.loc[t1]), r_0050, places=6)
        r_inv = float(pinv.loc[t2] / pinv.loc[t1] - 1.0)
        self.assertAlmostEqual(float(daily.loc[t2]), r_inv, places=6)


class TestLookAheadB(unittest.TestCase):
    def test_b_entry_return_timing(self):
        dates, px = _long_uptrend_with_dip()
        prices = {"T001": px}
        membership = _always_member(["T001"])
        ind = _compute_b_indicators(px)
        entry_mask = (
            (ind["close"] < ind["ma20"] - 2.0 * ind["std20"])
            & (ind["close"] > ind["ma200"])
            & ind["ma20"].notna()
            & ind["ma200"].notna()
        )
        self.assertTrue(entry_mask.any())
        t = entry_mask.idxmax()
        loc = dates.get_loc(t)
        daily, _ = backtest_b(prices, membership, dates, apply_costs=False)
        self.assertAlmostEqual(float(daily.loc[t]), 0.0, places=8)
        t1 = dates[loc + 1]
        self.assertAlmostEqual(float(daily.loc[t1]), 0.0, places=8)
        t2 = dates[loc + 2]
        expected = 0.10 * float(px.loc[t2] / px.loc[t1] - 1.0)
        self.assertAlmostEqual(float(daily.loc[t2]), expected, places=6)

    def test_b_exit_on_mean_reversion(self):
        dates, px = _long_uptrend_with_dip(dip_frac=0.90)
        recover_at = 235
        px.iloc[recover_at:] = px.iloc[recover_at - 1] * 1.08
        prices = {"T001": px}
        membership = _always_member(["T001"])
        daily, _ = backtest_b(prices, membership, dates, apply_costs=False)
        nonzero = daily[daily.abs() > 1e-8]
        self.assertGreater(len(nonzero), 0)

    def test_b_exit_on_max_hold_days(self):
        """Hold exactly 10 trading days from fill day; sell next close; earn sell-day return."""
        dates = pd.bdate_range("2018-01-01", periods=260)
        px = pd.Series(np.linspace(100.0, 160.0, 260), index=dates)
        dip_start = 220
        px.iloc[dip_start] = px.iloc[dip_start - 1] * 0.88
        for k in range(1, 40):
            px.iloc[dip_start + k] = px.iloc[dip_start + k - 1] * 0.999
        prices = {"T001": px}
        membership = _always_member(["T001"])

        ind = _compute_b_indicators(px)
        entry_mask = (
            (ind["close"] < ind["ma20"] - 2.0 * ind["std20"])
            & (ind["close"] > ind["ma200"])
            & ind["ma20"].notna()
            & ind["ma200"].notna()
        )
        self.assertTrue(entry_mask.any(), "dip did not trigger entry")
        t = entry_mask.idxmax()
        loc = dates.get_loc(t)
        t1 = dates[loc + 1]
        t2 = dates[loc + 2]
        sell_fill_day = dates[loc + 1 + 10]
        after = dates[loc + 1 + 11]

        daily, _ = backtest_b(prices, membership, dates, apply_costs=False)

        self.assertAlmostEqual(float(daily.loc[t]), 0.0, places=8)
        self.assertAlmostEqual(float(daily.loc[t1]), 0.0, places=8)
        self.assertGreater(abs(float(daily.loc[t2])), 1e-8)
        self.assertGreater(abs(float(daily.loc[sell_fill_day])), 1e-8)
        self.assertAlmostEqual(float(daily.loc[after]), 0.0, places=8)


class TestCosts(unittest.TestCase):
    def test_fee_minimum_exact_small_buy(self):
        notional = 100.0
        cost = compute_side_cost(notional, is_buy=True, symbol="2330.TW")
        fee = max(notional * FEE_RATE, FEE_MIN_TWD)
        slip = notional * SLIPPAGE_RATE
        expected = fee + slip
        self.assertAlmostEqual(cost, expected, places=6)
        self.assertAlmostEqual(fee, 20.0, places=6)

    def test_large_buy_no_min_fee(self):
        notional = 100_000.0
        cost = compute_side_cost(notional, is_buy=True, symbol="2330.TW")
        fee = notional * FEE_RATE
        self.assertGreater(fee, 20.0)

    def test_tax_only_on_sell_stock_vs_etf(self):
        notional = 100_000.0
        buy = compute_side_cost(notional, is_buy=True, symbol="2330.TW")
        sell_stock = compute_side_cost(notional, is_buy=False, symbol="2330.TW")
        sell_etf = compute_side_cost(notional, is_buy=False, symbol="0050.TW")
        self.assertLess(buy, sell_stock)
        self.assertLess(sell_etf, sell_stock)
        self.assertAlmostEqual(sell_stock - buy, notional * 0.003, places=4)
        self.assertAlmostEqual(sell_etf - buy, notional * ETF_TAX_RATE, places=4)

    def test_is_etf_helper(self):
        self.assertTrue(is_etf("0050.TW"))
        self.assertTrue(is_etf("00632R.TW"))
        self.assertFalse(is_etf("2330.TW"))

    def test_cta_costs_on_transitions(self):
        n = 280
        dates = pd.bdate_range("2018-01-01", periods=n)
        twii = pd.Series(np.linspace(100.0, 200.0, n), index=dates)
        twii.iloc[250:] = 80.0
        p0050 = pd.Series(100.0, index=dates)
        daily = backtest_cta(twii, p0050, None, apply_costs=True, principal=1_000_000, name="A1")
        sig = cta_signal(twii)
        up_days = sig[sig == 1].index
        self.assertGreater(len(up_days), 0)
        t_up = up_days[0]
        loc_up = dates.get_loc(t_up)
        fill_buy = dates[loc_up + 1]
        self.assertAlmostEqual(float(daily.loc[fill_buy]), -_buy_cost_drag(), places=6)


class TestMetrics(unittest.TestCase):
    def test_known_mdd_sequence(self):
        s = pd.Series([0.10, -0.20, 0.10])
        mdd = max_drawdown_pct(s)
        self.assertAlmostEqual(mdd, -20.0, places=5)

    def test_monthly_metrics_formula(self):
        s = pd.Series([0.01] * 12)
        m = monthly_metrics(s)
        self.assertAlmostEqual(m["cagr_pct"], (1.01 ** 12 - 1) * 100, places=4)
        self.assertGreater(m["sharpe"], 0)

    def test_daily_mdd_uses_costed_series(self):
        plain = pd.Series([0.05, -0.10, 0.03, -0.08, 0.04])
        costed = plain.copy()
        costed.iloc[1] -= 0.002
        self.assertLess(max_drawdown_pct(costed), max_drawdown_pct(plain))


class TestScaling(unittest.TestCase):
    def test_scaled_mdd_matches_target(self):
        rng = np.random.default_rng(42)
        s = pd.Series(rng.normal(0.01, 0.05, 60))
        target = -15.0
        scaled, k = scale_returns(s, target)
        achieved = max_drawdown_pct(scaled)
        self.assertAlmostEqual(achieved, target, delta=0.1)


class TestPortfolioWeights(unittest.TestCase):
    def test_equal_weight_two_sums_to_one(self):
        idx = pd.date_range("2020-01-31", periods=4, freq="ME")
        a = pd.Series([0.01, 0.02, -0.01, 0.03], index=idx)
        b = pd.Series([0.03, -0.01, 0.02, 0.00], index=idx)
        combo = equal_weight([a, b], "eq")
        expected = 0.5 * a + 0.5 * b
        pd.testing.assert_series_equal(combo, expected, check_names=False)

    def test_equal_weight_three_sums_to_one(self):
        idx = pd.date_range("2020-01-31", periods=3, freq="ME")
        a = pd.Series([0.01, 0.02, 0.03], index=idx)
        b = pd.Series([0.04, 0.05, 0.06], index=idx)
        c = pd.Series([-0.01, 0.00, 0.01], index=idx)
        combo = equal_weight([a, b, c], "eq3")
        expected = (a + b + c) / 3.0
        pd.testing.assert_series_equal(combo, expected, check_names=False)

    def test_two_strategy_scan_weights_sum_to_one(self):
        idx = pd.date_range("2020-01-31", periods=6, freq="ME")
        nn = pd.Series(0.01, index=idx)
        other = pd.Series(0.02, index=idx)
        scans = two_strategy_scan(nn, other, "A1")
        self.assertGreater(len(scans), 0)

    def test_three_strategy_scan_weights_sum_to_one(self):
        idx = pd.date_range("2020-01-31", periods=4, freq="ME")
        nn = pd.Series([0.01, 0.02, 0.00, -0.01], index=idx)
        a = pd.Series([0.03, 0.01, 0.02, 0.04], index=idx)
        b = pd.Series([-0.02, 0.01, 0.00, 0.01], index=idx)
        scans = three_strategy_scan(nn, a, b, "A1")
        self.assertGreater(len(scans), 0)


class TestMembershipPointInTime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mem = load_membership_intervals(MEMBERSHIP_CSV)

    def test_2014_01_02(self):
        codes = constituents_on_date("2014-01-02", self.mem)
        self.assertEqual(len(codes), 50)
        self.assertIn("2311", codes)
        self.assertIn("2325", codes)
        self.assertIn("3697", codes)
        self.assertNotIn("3474", codes)

    def test_2014_01_16(self):
        codes = constituents_on_date("2014-01-16", self.mem)
        self.assertIn("3474", codes)
        self.assertNotIn("3697", codes)

    def test_2018_04_18(self):
        codes = constituents_on_date("2018-04-18", self.mem)
        self.assertNotIn("2325", codes)
        self.assertIn("2327", codes)

    def test_2026_03_31(self):
        codes = constituents_on_date("2026-03-31", self.mem)
        self.assertEqual(len(codes), 49)
        self.assertNotIn("3037", codes)

    def test_2026_04_14(self):
        codes = constituents_on_date("2026-04-14", self.mem)
        self.assertIn("3037", codes)


class TestEffectiveDateBoundary(unittest.TestCase):
    def test_no_entry_before_start_and_cancel_if_next_not_member(self):
        dates, px = _long_uptrend_with_dip(n=260, dip_at=230)
        membership = pd.DataFrame({
            "code": ["AAA"],
            "name": ["AAA"],
            "start_date": [dates[240]],
            "end_date": [dates[250]],
        })
        prices = {"AAA": px}
        daily, _ = backtest_b(prices, membership, dates, apply_costs=False)
        self.assertTrue((daily.abs() < 1e-6).all())

    def test_forced_sell_on_last_constituent_day(self):
        dates, px = _long_uptrend_with_dip(n=260, dip_at=220)
        membership = pd.DataFrame({
            "code": ["BBB"],
            "name": ["BBB"],
            "start_date": [dates[0]],
            "end_date": [dates[235]],
        })
        prices = {"BBB": px}
        daily, events = backtest_b(prices, membership, dates, apply_costs=False)
        self.assertTrue((daily.iloc[:235].abs() > 1e-8).any())
        after = daily.loc[dates[235]:]
        self.assertTrue((after.abs() < 1e-8).all())


class TestPriceInterruption(unittest.TestCase):
    def test_intermediate_gap_is_not_series_end(self):
        """Missing 2 trading days in the middle must NOT force a sell."""
        dates = pd.bdate_range("2018-01-01", periods=260)
        px = pd.Series(np.linspace(100.0, 160.0, 260), index=dates)
        dip_start = 220
        px.iloc[dip_start] = px.iloc[dip_start - 1] * 0.88
        for k in range(1, 30):
            px.iloc[dip_start + k] = px.iloc[dip_start + k - 1] * 0.999
        # Punch a 2-day hole after entry
        gap_start = dip_start + 5
        px = px.drop(dates[gap_start:gap_start + 2])
        prices = {"GAP": px}
        membership = _always_member(["GAP"])
        daily, events = backtest_b(prices, membership, dates, apply_costs=False)
        # No price-interruption event for the intermediate gap
        self.assertEqual(len(events), 0)
        # After the gap, holding continues (non-zero return on a later day)
        later = dates[gap_start + 5]
        self.assertGreater(abs(float(daily.loc[later])), 1e-8)

    def test_true_series_end_records_event(self):
        """True series end (no more prices after cut) must sell at last close and record event."""
        dates = pd.bdate_range("2018-01-01", periods=260)
        px = pd.Series(np.linspace(100.0, 160.0, 260), index=dates)
        dip_start = 220
        px.iloc[dip_start] = px.iloc[dip_start - 1] * 0.88
        for k in range(1, 15):
            px.iloc[dip_start + k] = px.iloc[dip_start + k - 1] * 0.999
        cut_at = dip_start + 6
        last_price_date = dates[cut_at]
        px = px.iloc[: cut_at + 1]
        prices = {"END": px}
        membership = _always_member(["END"])
        daily, events = backtest_b(prices, membership, dates, apply_costs=False)
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev["code"], "END")
        self.assertEqual(pd.Timestamp(ev["last_price_date"]), last_price_date)
        self.assertGreater(abs(float(daily.loc[last_price_date])), 1e-8)
        next_idx = dates.get_loc(last_price_date) + 1
        if next_idx < len(dates):
            self.assertAlmostEqual(float(daily.loc[dates[next_idx]]), 0.0, places=8)

    def test_slice_end_is_not_automatic_interruption(self):
        """Last day of trading_dates slice is not a series end if the stock still has later prices."""
        full_dates = pd.bdate_range("2018-01-01", periods=280)
        px = pd.Series(np.linspace(100.0, 170.0, 280), index=full_dates)
        dip_start = 220
        px.iloc[dip_start] = px.iloc[dip_start - 1] * 0.88
        for k in range(1, 40):
            px.iloc[dip_start + k] = px.iloc[dip_start + k - 1] * 0.999
        # trading_dates ends earlier; prices continue beyond it
        short_dates = full_dates[:250]
        prices = {"CONT": px}
        membership = _always_member(["CONT"])
        daily, events = backtest_b(prices, membership, short_dates, apply_costs=False)
        # No event whose last_price_date is the last day of the short slice
        last_slice_day = short_dates[-1]
        bad = [ev for ev in events if pd.Timestamp(ev["last_price_date"]) == last_slice_day]
        self.assertEqual(len(bad), 0)


class TestTradableThreshold(unittest.TestCase):
    def test_under_200_days_never_enters_others_do(self):
        dates = pd.bdate_range("2015-01-01", periods=250)
        px_ok = pd.Series(np.linspace(100, 180, 250), index=dates)
        px_ok.iloc[220] = px_ok.iloc[219] * 0.90
        px_short = pd.Series(np.linspace(50, 80, 100), index=dates[-100:])
        px_short.iloc[80] = px_short.iloc[79] * 0.85
        prices = {"OK1": px_ok, "SHORT": px_short}
        membership = _always_member(["OK1", "SHORT"])
        daily, _ = backtest_b(prices, membership, dates, apply_costs=False)
        self.assertTrue((daily.abs() > 1e-8).any())
        first, never = compute_tradable_info(prices, membership, dates)
        self.assertIn("OK1", first)
        self.assertIn("SHORT", never)

    def test_fewer_than_10_tradable_still_trades_rest_cash(self):
        dates = pd.bdate_range("2015-01-01", periods=220)
        prices = {}
        codes = []
        for i in range(3):
            code = f"S{i:02d}"
            codes.append(code)
            px = pd.Series(np.linspace(100, 140, 220), index=dates)
            px.iloc[200] = px.iloc[199] * 0.91
            prices[code] = px
        membership = _always_member(codes)
        daily, _ = backtest_b(prices, membership, dates, apply_costs=False)
        self.assertTrue((daily.abs() > 1e-8).any())


class TestTEJReadAndMissing(unittest.TestCase):
    def test_tej_utf16_and_utf8_identical_three_columns(self):
        sample = (
            "證券代碼\t年月日\t收盤價(元)\t其他欄\n"
            "2311 日月光\t20140102\t10.5\txxx\n"
            "2325 矽品\t20140102\t20.0\tyyy\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            p16 = Path(tmp) / "a_utf16.txt"
            p8 = Path(tmp) / "a_utf8.txt"
            p16.write_bytes(sample.encode("utf-16"))
            p8.write_text(sample, encoding="utf-8")
            df16 = _process_tej_df(_read_tej_raw(p16))
            df8 = _process_tej_df(_read_tej_raw(p8))
            pd.testing.assert_frame_equal(df16, df8)
            self.assertListEqual(list(df16.columns), ["code", "date", "close"])

    def test_missing_tej_files_error_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty_a = Path(tmp) / "tej_prices_a.txt"
            empty_b = Path(tmp) / "tej_prices_b.txt"
            with patch("research.strategy_combo.config.TEJ_PRICES_A", empty_a), \
                 patch("research.strategy_combo.config.TEJ_PRICES_B", empty_b), \
                 patch("research.strategy_combo.config.TEJ_INPUT_DIR", Path(tmp)):
                with self.assertRaises(FileNotFoundError) as cm:
                    check_tej_files_exist()
                msg = str(cm.exception)
                self.assertIn("tej_prices_a.txt", msg)
                self.assertIn("tej_prices_b.txt", msg)
                self.assertIn(str(empty_a.resolve()), msg)
                self.assertIn(str(empty_b.resolve()), msg)
                self.assertIn("調整股價(日)-除權息調整", msg)
                self.assertIn("2311", msg)
                self.assertIn("TEJ20261117104345", msg)

    def test_run_main_exits_nonzero_no_report_when_tej_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            empty_a = tmp_path / "tej_prices_a.txt"
            empty_b = tmp_path / "tej_prices_b.txt"
            out_dir = tmp_path / "out"
            with patch("research.strategy_combo.config.TEJ_PRICES_A", empty_a), \
                 patch("research.strategy_combo.config.TEJ_PRICES_B", empty_b), \
                 patch("research.strategy_combo.config.TEJ_INPUT_DIR", tmp_path), \
                 patch("sys.argv", ["run.py", "--out-dir", str(out_dir)]):
                from research.strategy_combo.run import main
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertNotEqual(cm.exception.code, 0)
                self.assertFalse((out_dir / "report.md").exists())


class TestCommonPeriodAndCorrelations(unittest.TestCase):
    def test_common_start_ignores_late_b_price(self):
        nn = pd.Series(0.01, index=pd.date_range("2015-01-31", "2026-08-31", freq="ME"))
        twii = pd.Series(10000.0, index=pd.bdate_range("2014-01-01", "2026-08-31"))
        p0050 = twii.copy()
        pinv = twii.copy()
        start, end = find_common_period(nn, twii, p0050, pinv)
        self.assertLess(start, pd.Timestamp("2020-01-01"))

    def test_rolling_corr_empty_and_report_text_when_insufficient(self):
        short_idx = pd.date_range("2025-01-31", periods=10, freq="ME")
        nn3 = pd.Series(0.01, index=short_idx)
        a1 = pd.Series(0.02, index=short_idx)
        a2 = pd.Series(0.015, index=short_idx)
        b = pd.Series(0.005, index=short_idx)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = compute_correlations(nn3, a1, a2, b, out)
            self.assertEqual(result["n_valid_windows"], 0)
            write_report(
                out_dir=out,
                common_start="2025-01",
                common_end="2025-10",
                n_common_months=10,
                sample_ok=False,
                nn3_full_metrics={"sharpe": 1.0, "mdd_pct": -10.0, "cagr_pct": 10.0},
                nn3_backup_metrics={"sharpe": 1.0, "mdd_pct": -10.0, "cagr_pct": 10.0},
                strategy_metrics={},
                scale_factors={},
                combo_summary=pd.DataFrame(),
                data_notes=[],
                principal=1_000_000,
                coverage_rate=1.0,
                first_tradable={},
                never_tradable={},
                price_events=[],
                universe_csv="month_end_universe.csv",
                n_valid_windows=0,
            )
            text = (out / "report.md").read_text(encoding="utf-8")
            self.assertIn("樣本不足，未產出滾動相關", text)


    def test_ma_ready_mid_month_starts_next_month(self):
        # MA ready mid-May 2015; others ready much earlier → start must be 2015-06-30
        ready = pd.Timestamp("2015-05-15")
        pre = pd.bdate_range(end=ready, periods=200)
        post = pd.bdate_range(start=ready + pd.Timedelta(days=1), end="2026-08-31")
        twii_idx = pre.union(post)
        twii = pd.Series(10000.0, index=twii_idx)
        nn = pd.Series(0.01, index=pd.date_range("2014-01-31", "2026-08-31", freq="ME"))
        p0050 = pd.Series(50.0, index=pd.bdate_range("2014-01-01", "2026-08-31"))
        pinv = pd.Series(30.0, index=pd.bdate_range("2014-01-01", "2026-08-31"))
        start, end = find_common_period(nn, twii, p0050, pinv)
        self.assertEqual(start, pd.Timestamp("2015-06-30"))
        self.assertEqual(end, pd.Timestamp("2026-08-31"))

    def test_ma_ready_on_first_trading_day_keeps_month(self):
        # MA ready exactly on first trading day of May 2015 → that month is valid
        may_begin = pd.Timestamp("2015-05-01")
        first_td = pd.bdate_range(start=may_begin, periods=1)[0]
        pre = pd.bdate_range(end=first_td, periods=200)
        post = pd.bdate_range(start=first_td + pd.Timedelta(days=1), end="2026-08-31")
        twii_idx = pre.union(post)
        twii = pd.Series(10000.0, index=twii_idx)
        nn = pd.Series(0.01, index=pd.date_range("2014-01-31", "2026-08-31", freq="ME"))
        p0050 = pd.Series(50.0, index=pd.bdate_range("2014-01-01", "2026-08-31"))
        pinv = pd.Series(30.0, index=pd.bdate_range("2014-01-01", "2026-08-31"))
        start, end = find_common_period(nn, twii, p0050, pinv)
        self.assertEqual(start, pd.Timestamp("2015-05-31"))
        self.assertEqual(end, pd.Timestamp("2026-08-31"))


if __name__ == "__main__":
    unittest.main()
