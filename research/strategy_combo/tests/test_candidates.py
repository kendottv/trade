"""Tests for LV and XA candidate strategies (AC-15).

All synthetic data, temp directories, no network, no TEJ files required.
"""
import sys
import tempfile
import unittest
import io
import contextlib
from pathlib import Path
from unittest.mock import patch, MagicMock

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from research.strategy_combo.lowvol import (  # noqa: E402
    compute_side_cost_03,
    select_lowvol,
    backtest_lowvol,
    load_industry_map,
    WEIGHT_PER,
)
from research.strategy_combo.xamom import (  # noqa: E402
    filter_pre_listing,
    compute_momentum,
    select_xa,
    backtest_xa,
    build_month_end_prices,
    a1_daily_03,
)
from research.strategy_combo.candidates_report import (  # noqa: E402
    build_combo_table,
    compute_monthly_correlations,
    compute_daily_correlations,
    _plot_yearly_corr,
)
from research.strategy_combo.metrics import monthly_metrics  # noqa: E402
from research.strategy_combo.run_candidates import (  # noqa: E402
    _slice_daily,
    _avg_monthly_turnover,
    _months_inclusive,
    _xa_holdings_rows,
)


class TestLowVol(unittest.TestCase):
    def setUp(self):
        self.dates = pd.bdate_range("2020-01-01", periods=400)
        self.membership = pd.DataFrame({
            "code": ["A", "B", "C", "D", "E"],
            "name": ["A", "B", "C", "D", "E"],
            "start_date": pd.to_datetime("2019-01-01"),
            "end_date": pd.NaT,
        })
        self.industry = {"A": "半導體業", "B": "半導體業", "C": "半導體業", "D": "半導體業", "E": "金融保險業"}

    def _make_prices(self, n=400, vols=None):
        if vols is None:
            vols = {"A": 0.01, "B": 0.02, "C": 0.03, "D": 0.04, "E": 0.015}
        prices = {}
        rng = np.random.default_rng(42)
        for code, vol in vols.items():
            ret = rng.normal(0, vol, n)
            px = 100 * np.cumprod(1 + ret)
            prices[code] = pd.Series(px, index=self.dates[:n])
        return prices

    def test_no_lookahead(self):
        prices_base = self._make_prices()
        # find a real month-end after day 300
        month_ends = self.dates.to_series().groupby(self.dates.to_period("M")).max()
        t_candidates = [d for d in month_ends if d >= self.dates[300]]
        t = t_candidates[0]
        t_idx = self.dates.get_loc(t)
        t1 = self.dates[t_idx + 1]
        t2 = self.dates[t_idx + 2]
        mem = self.membership.copy()
        mem.loc[mem["code"] == "A", "start_date"] = t
        # unique industry so selected
        ind = self.industry.copy()
        ind["A"] = "獨特產業"
        daily_base, _, holds_base, _, _ = backtest_lowvol(
            prices_base, mem, ind, self.dates, apply_costs=False
        )
        prices_jump = {k: v.copy() for k, v in prices_base.items()}
        prices_jump["A"].loc[t1] = prices_jump["A"].loc[t] * 1.5
        daily_jump, _, _, _, _ = backtest_lowvol(
            prices_jump, mem, ind, self.dates, apply_costs=False
        )
        self.assertAlmostEqual(daily_jump.loc[t1], daily_base.loc[t1], places=8)
        self.assertNotAlmostEqual(daily_jump.loc[t2], daily_base.loc[t2], places=5)

    def test_timing_not_constituent_next(self):
        prices = self._make_prices()
        mem = self.membership.copy()
        mem.loc[mem["code"] == "B", "end_date"] = self.dates[300]
        t = self.dates[300]
        t_next = self.dates[301]
        selected = select_lowvol(t, t_next, prices, mem, self.industry)
        self.assertNotIn("B", selected)

    def test_vol_window_boundary(self):
        short = pd.bdate_range("2020-01-01", periods=250)
        prices_short = {"A": pd.Series(np.linspace(100, 120, 250), index=short)}
        mem = self.membership[self.membership["code"] == "A"]
        t = short[-1]
        t_next = short[-1] + pd.Timedelta(days=1)
        selected = select_lowvol(t, t_next, prices_short, mem, self.industry)
        self.assertEqual(selected, [])
        long = pd.bdate_range("2020-01-01", periods=251)
        prices_long = {"A": pd.Series(np.linspace(100, 120, 251), index=long)}
        t = long[-1]
        t_next = long[-1] + pd.Timedelta(days=1)
        selected = select_lowvol(t, t_next, prices_long, mem, self.industry)
        self.assertIn("A", selected)

    def test_industry_cap(self):
        prices = self._make_prices(vols={"A": 0.01, "B": 0.011, "C": 0.012, "D": 0.013, "E": 0.02})
        t = self.dates[300]
        t_next = self.dates[301]
        selected = select_lowvol(t, t_next, prices, self.membership, self.industry)
        semi = [c for c in selected if self.industry.get(c) == "半導體業"]
        self.assertLessEqual(len(semi), 3)
        self.assertNotIn("D", selected)
        self.assertIn("E", selected)

    def test_industry_missing_raises(self):
        prices = self._make_prices(vols={"A": 0.01, "F": 0.02})
        mem = pd.concat([
            self.membership,
            pd.DataFrame({"code": ["F"], "name": ["F"], "start_date": pd.to_datetime("2019-01-01"), "end_date": pd.NaT})
        ], ignore_index=True)
        ind = self.industry.copy()
        with self.assertRaises(RuntimeError):
            select_lowvol(self.dates[300], self.dates[301], prices, mem, ind)

    def test_forced_sell_on_removal(self):
        prices = self._make_prices(n=400)
        mem = self.membership.copy()
        last_cons = self.dates[319]
        mem.loc[mem["code"] == "A", "end_date"] = self.dates[320]
        daily, monthly, holds, events, _ = backtest_lowvol(
            prices, mem, self.industry, self.dates, apply_costs=False
        )
        self.assertTrue(any(e["code"] == "A" and e["date"] == last_cons for e in events))
        held_before = any("A" in h.get("codes", []) for h in holds if h["date"] < last_cons)
        self.assertTrue(held_before)
        after = [h for h in holds if h["date"] > last_cons]
        if after:
            self.assertNotIn("A", after[0].get("codes", []))
            n_before = next((h["n"] for h in reversed(holds) if h["date"] < last_cons), 0)
            self.assertEqual(after[0]["n"], n_before - 1)

    def test_insufficient_names_weight_10pct(self):
        prices = self._make_prices(vols={"A": 0.01, "B": 0.02, "C": 0.03})
        mem = self.membership[self.membership["code"].isin(["A", "B", "C"])]
        ind = {k: self.industry[k] for k in ["A", "B", "C"]}
        daily, monthly, holds, events, _ = backtest_lowvol(
            prices, mem, ind, self.dates, apply_costs=False
        )
        three = [h for h in holds if h.get("n") == 3]
        self.assertGreater(len(three), 0)
        for h in three:
            self.assertAlmostEqual(sum(h["weights"].values()), 0.3, places=4)
            for w in h["weights"].values():
                self.assertAlmostEqual(w, WEIGHT_PER, places=4)

    def test_holdings_once_per_month(self):
        prices = self._make_prices()
        daily, monthly, holds, events, _ = backtest_lowvol(
            prices, self.membership, self.industry, self.dates, apply_costs=False
        )
        self.assertGreater(len(holds), 0)
        months = [pd.Timestamp(h["date"]).to_period("M") for h in holds]
        self.assertEqual(len(months), len(set(months)))
        for h in holds:
            d = pd.Timestamp(h["date"])
            self.assertEqual(d, self.dates[self.dates.to_period("M") == d.to_period("M")].max())


class TestXA(unittest.TestCase):
    def test_filter_pre_listing(self):
        dates = pd.date_range("2015-01-01", periods=20, freq="B")
        df = pd.DataFrame({"Close": range(20), "Volume": [0]*5 + [100]*15}, index=dates)
        listing = dates[10]
        filtered, n = filter_pre_listing(df, listing)
        self.assertEqual(n, 10)
        self.assertTrue((filtered.index >= listing).all())

    def test_momentum_calculation(self):
        dates = pd.date_range("2020-01-31", periods=15, freq="ME")
        px = pd.Series(np.linspace(100, 150, 15), index=dates)
        t = dates[-1]
        mom = compute_momentum(px, t)
        p_t = px.iloc[-1]
        r3 = p_t / px.iloc[-4] - 1
        r6 = p_t / px.iloc[-7] - 1
        r12 = p_t / px.iloc[-13] - 1
        expected = (r3 + r6 + r12) / 3
        self.assertAlmostEqual(mom, expected, places=6)

    def test_month_end_not_calendar(self):
        dates = pd.bdate_range("2016-01-01", "2018-12-31")
        prices = {
            "0050": pd.Series(np.linspace(100, 120, len(dates)), index=dates),
            "00679B": pd.Series(np.linspace(100, 130, len(dates)), index=dates),
            "00635U": pd.Series(np.linspace(100, 110, len(dates)), index=dates),
        }
        listing = {c: dates[0] for c in prices}
        daily, monthly, holds, hold_m, first_perf, _ = backtest_xa(
            prices, listing, dates, apply_costs=False
        )
        self.assertIsNotNone(first_perf)
        # check specific non-calendar ends
        hold_dates = [pd.Timestamp(h["date"]) for h in holds]
        self.assertTrue(any(d.month == 4 and d.day == 28 and d.year == 2017 for d in hold_dates))
        self.assertTrue(any(d.month == 3 and d.day == 30 and d.year == 2018 for d in hold_dates))
        # next after those is not empty
        for target in [pd.Timestamp("2017-04-28"), pd.Timestamp("2018-03-30")]:
            after = [h for h in holds if pd.Timestamp(h["date"]) > target]
            if after:
                self.assertGreater(after[0].get("n", 0), 0)

    def test_select_top2_ties_by_code(self):
        dates = pd.date_range("2020-01-31", periods=15, freq="ME")
        px_a = pd.Series(np.linspace(100, 130, 15), index=dates)  # highest
        px_b = pd.Series(np.linspace(100, 120, 15), index=dates)
        px_c = pd.Series(np.linspace(100, 120, 15), index=dates)  # same as B
        me = {"C": px_c, "B": px_b, "A": px_a}
        t = dates[-1]
        w = select_xa(t, me)
        self.assertIn("A", w)
        self.assertIn("B", w)
        self.assertNotIn("C", w)

    def test_absolute_momentum_cash(self):
        dates = pd.date_range("2020-01-31", periods=15, freq="ME")
        px_neg = pd.Series(np.linspace(100, 80, 15), index=dates)
        px_pos = pd.Series(np.linspace(100, 120, 15), index=dates)
        me = {"NEG": px_neg, "POS": px_pos}
        t = dates[-1]
        w = select_xa(t, me)
        self.assertEqual(w.get("NEG", 0), 0.0)
        self.assertGreater(w.get("POS", 0), 0)

    def test_insufficient_data_no_signal_in_monthly(self):
        dates = pd.bdate_range("2020-01-01", periods=450)
        prices = {
            "A": pd.Series(np.linspace(100, 110, len(dates)), index=dates),
            "B": pd.Series(np.linspace(100, 120, len(dates)), index=dates),
            "C": pd.Series(np.linspace(100, 105, len(dates)), index=dates),
        }
        listing = {c: dates[0] for c in prices}
        daily, monthly, holds, hold_m, first_perf, _ = backtest_xa(
            prices, listing, dates, apply_costs=False
        )
        self.assertIsNotNone(first_perf)
        self.assertEqual(monthly.index.min().to_period("M"), first_perf.to_period("M"))
        early = monthly[monthly.index < first_perf]
        self.assertTrue(early.empty)
        early_holds = [
            h for h in holds
            if pd.Timestamp(h["date"]).to_period("M") < first_perf.to_period("M")
        ]
        for h in early_holds:
            self.assertEqual(h.get("n", 0), 0)

    def test_xa_avg_holdings_two(self):
        dates = pd.bdate_range("2016-01-01", "2019-12-31")
        prices = {
            "0050": pd.Series(np.linspace(100, 150, len(dates)), index=dates),
            "00679B": pd.Series(np.linspace(100, 140, len(dates)), index=dates),
            "00635U": pd.Series(np.linspace(100, 130, len(dates)), index=dates),
        }
        listing = {c: dates[0] for c in prices}
        daily, monthly, holds, hold_m, first_perf, _ = backtest_xa(
            prices, listing, dates, apply_costs=False
        )
        self.assertIsNotNone(first_perf)
        self.assertGreater(len(holds), 0)
        start_per = first_perf.to_period("M")
        period_holds = [
            h for h in holds
            if pd.Timestamp(h["date"]).to_period("M") >= start_per
        ]
        self.assertGreater(len(period_holds), 0)
        avg_n = np.mean([h.get("n", 0) for h in period_holds])
        self.assertAlmostEqual(avg_n, 2.0, places=5)

    def test_xa_end_limit_holdings(self):
        dates = pd.bdate_range("2016-01-01", "2019-12-31")
        prices = {
            "0050": pd.Series(np.linspace(100, 150, len(dates)), index=dates),
            "00679B": pd.Series(np.linspace(100, 140, len(dates)), index=dates),
            "00635U": pd.Series(np.linspace(100, 130, len(dates)), index=dates),
        }
        listing = {c: dates[0] for c in prices}
        end_lim = pd.Timestamp("2018-12-31")
        daily, monthly, holds, hold_m, first_perf, _ = backtest_xa(
            prices, listing, dates, apply_costs=False, end_limit=end_lim
        )
        self.assertIsNotNone(first_perf)
        self.assertGreater(len(holds), 0)
        max_months = (end_lim.to_period("M") - first_perf.to_period("M")).n + 1
        total_hold = sum(hold_m.values())
        self.assertLessEqual(total_hold, max_months * 2)
        for h in holds:
            self.assertLessEqual(pd.Timestamp(h["date"]), end_lim)

    def test_xa_cost_on_rebalance(self):
        # design prices so one rebalance from 00679B to 00635U
        dates = pd.bdate_range("2016-01-01", "2018-12-31")
        n = len(dates)
        # 0050 steadily up, 00679B high early then flat, 00635U low early then high later
        p0050 = pd.Series(np.linspace(100, 200, n), index=dates)
        p679 = pd.Series(np.concatenate([np.linspace(100, 180, n//2), np.linspace(180, 160, n - n//2)]), index=dates)
        p635 = pd.Series(np.concatenate([np.linspace(100, 110, n//2), np.linspace(110, 200, n - n//2)]), index=dates)
        prices = {"0050": p0050, "00679B": p679, "00635U": p635}
        listing = {c: dates[0] for c in prices}
        daily_nc, _, holds_nc, _, _, traded_nc = backtest_xa(prices, listing, dates, apply_costs=False)
        daily_c, _, _, _, _, traded_c = backtest_xa(prices, listing, dates, apply_costs=True)
        # find the specific rebalance: from {0050:0.5, 00679B:0.5} to {0050:0.5, 00635U:0.5}
        rebal_fill_day = None
        for i in range(len(holds_nc) - 1):
            prev_w = holds_nc[i].get("weights", {})
            next_w = holds_nc[i + 1].get("weights", {})
            if (abs(prev_w.get("0050", 0) - 0.5) < 1e-9 and abs(prev_w.get("00679B", 0) - 0.5) < 1e-9
                    and abs(next_w.get("0050", 0) - 0.5) < 1e-9 and abs(next_w.get("00635U", 0) - 0.5) < 1e-9
                    and "00679B" not in next_w and "00635U" not in prev_w):
                next_date = pd.Timestamp(holds_nc[i + 1]["date"])
                # fill day = first trading day of the month of the next holding record
                month_start = next_date.to_period("M").to_timestamp()
                candidates = dates[(dates >= month_start) & (dates.to_period("M") == next_date.to_period("M"))]
                if len(candidates):
                    rebal_fill_day = candidates[0]
                    break
        self.assertIsNotNone(rebal_fill_day, "no rebalance from 00679B to 00635U found")
        self.assertAlmostEqual(traded_nc.loc[rebal_fill_day], 1.0, places=5)
        diff = daily_nc.loc[rebal_fill_day] - daily_c.loc[rebal_fill_day]
        self.assertAlmostEqual(diff, 0.003925, places=5)

    def test_first_perf_month_calendar_end_not_trading_day(self):
        """First performance month is 2018-02 whose calendar end is not a trading day; must count it."""
        # start prices ~2017-01 so first signal month ~2018-01, first perf month = 2018-02
        all_bdays = pd.bdate_range("2017-01-03", "2019-12-31")
        holiday = pd.Timestamp("2018-02-28")
        dates = all_bdays[all_bdays != holiday]
        self.assertNotIn(holiday, dates)
        last_feb = dates[dates.to_period("M") == "2018-02"].max()
        self.assertEqual(last_feb, pd.Timestamp("2018-02-27"))
        prices = {
            "0050": pd.Series(np.linspace(100, 180, len(dates)), index=dates),
            "00679B": pd.Series(np.linspace(100, 170, len(dates)), index=dates),
            "00635U": pd.Series(np.linspace(100, 160, len(dates)), index=dates),
        }
        listing = {c: dates[0] for c in prices}
        daily, monthly, holds, hold_m, first_perf, _ = backtest_xa(
            prices, listing, dates, apply_costs=False
        )
        self.assertIsNotNone(first_perf)
        # must be exactly 2018-02; if not, fail (no if)
        self.assertEqual(first_perf.to_period("M"), pd.Period("2018-02", freq="M"))
        # holdings log must contain the last trading day of that month
        feb_holds = [h for h in holds if pd.Timestamp(h["date"]) == last_feb]
        self.assertEqual(len(feb_holds), 1)
        self.assertGreater(feb_holds[0].get("n", 0), 0)
        # hold_months must include 2018-02: total asset-months == months_from_first_to_end * 2
        end_ts = pd.Timestamp("2019-12-31")
        n_months = (end_ts.to_period("M") - first_perf.to_period("M")).n + 1
        total = sum(hold_m.values())
        self.assertEqual(total, n_months * 2)

    def test_xa_holdings_csv_includes_first_month_non_trading_end(self):
        """xa_holdings rows must include 2018-02-27 when calendar end is not a trading day."""
        all_bdays = pd.bdate_range("2017-01-03", "2019-12-31")
        holiday = pd.Timestamp("2018-02-28")
        dates = all_bdays[all_bdays != holiday]
        last_feb = dates[dates.to_period("M") == "2018-02"].max()
        self.assertEqual(last_feb, pd.Timestamp("2018-02-27"))
        prices = {
            "0050": pd.Series(np.linspace(100, 180, len(dates)), index=dates),
            "00679B": pd.Series(np.linspace(100, 170, len(dates)), index=dates),
            "00635U": pd.Series(np.linspace(100, 160, len(dates)), index=dates),
        }
        listing = {c: dates[0] for c in prices}
        daily, monthly, holds, hold_m, first_perf, _ = backtest_xa(
            prices, listing, dates, apply_costs=False
        )
        self.assertIsNotNone(first_perf)
        self.assertEqual(first_perf.to_period("M"), pd.Period("2018-02", freq="M"))
        end_ts = pd.Timestamp("2019-12-31")
        rows = _xa_holdings_rows(holds, first_perf, end_ts)
        self.assertGreater(len(rows), 0)
        # must contain the last trading day of the first performance month
        feb_rows = [r for r in rows if pd.Timestamp(r["date"]) == last_feb]
        self.assertGreater(len(feb_rows), 0)
        # number of distinct months in the rows equals inclusive months from first_perf to end
        months_in_rows = {pd.Timestamp(r["date"]).to_period("M") for r in rows}
        n_months = (end_ts.to_period("M") - first_perf.to_period("M")).n + 1
        self.assertEqual(len(months_in_rows), n_months)


class TestCostsAndCombo(unittest.TestCase):
    def test_cost_always_03_and_min_fee(self):
        notional = 1000.0
        cost_buy = compute_side_cost_03(notional, is_buy=True)
        expected_buy = 20.0 + notional * 0.001
        self.assertAlmostEqual(cost_buy, expected_buy, places=2)
        cost_sell = compute_side_cost_03(notional, is_buy=False)
        expected_sell = 20.0 + notional * 0.003 + notional * 0.001
        self.assertAlmostEqual(cost_sell, expected_sell, places=2)

    def test_combo_weights_and_diffs(self):
        idx = pd.date_range("2020-01-31", periods=24, freq="ME")
        rng = np.random.default_rng(1)
        nn3 = pd.Series(rng.normal(0.01, 0.05, 24), index=idx)
        a1 = pd.Series(rng.normal(0.008, 0.04, 24), index=idx)
        lv = pd.Series(rng.normal(0.009, 0.03, 24), index=idx)
        tbl = build_combo_table(nn3, a1, lv, label="LV")
        self.assertIn("baseline_LV", tbl.index)
        self.assertIn("LV_10", tbl.index)
        base = 0.6 * nn3 + 0.4 * a1
        combo = 0.9 * base + 0.1 * lv
        m_c = monthly_metrics(combo)
        m_b = monthly_metrics(base)
        self.assertAlmostEqual(tbl.loc["LV_10", "sharpe_diff"], m_c["sharpe"] - m_b["sharpe"], places=5)
        self.assertAlmostEqual(tbl.loc["LV_10", "mdd_diff_pp"], m_c["mdd_pct"] - m_b["mdd_pct"], places=5)
        with self.assertRaises(ValueError):
            build_combo_table(nn3, a1, lv, base_weights=(0.6, 0.5), label="bad")
        with self.assertRaises(ValueError):
            build_combo_table(nn3, a1, lv, weights=(1.2,), label="bad")
        lv_short = lv.iloc[:-1]
        with self.assertRaises(RuntimeError):
            build_combo_table(nn3, a1, lv_short, expected_months=24, label="short")


class TestCorrelations(unittest.TestCase):
    def test_rolling_insufficient_left_empty(self):
        idx = pd.date_range("2020-01-31", periods=20, freq="ME")
        s1 = pd.Series(np.random.randn(20), index=idx)
        s2 = pd.Series(np.random.randn(20), index=idx)
        with tempfile.TemporaryDirectory() as td:
            res = compute_monthly_correlations({"A": s1, "B": s2}, Path(td), "test")
            self.assertEqual(res["n_valid_windows"], 0)
            csv = Path(td) / "corr_test_monthly_rolling36.csv"
            self.assertTrue(csv.exists())
            df = pd.read_csv(csv, encoding="utf-8", index_col=0)
            self.assertEqual(len(df), 20)
            pair_cols = [c for c in df.columns if "_" in c]
            if pair_cols:
                self.assertTrue(df[pair_cols].isna().all().all())

    def test_daily_no_nn3(self):
        idx = pd.bdate_range("2020-01-01", periods=300)
        s1 = pd.Series(np.random.randn(300), index=idx)
        s2 = pd.Series(np.random.randn(300), index=idx)
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                compute_daily_correlations({"LV": s1, "NN3": s2}, Path(td), "d")

    def test_yearly_png_has_lines(self):
        idx = pd.date_range("2020-01-31", periods=24, freq="ME")
        s1 = pd.Series(np.random.randn(24), index=idx)
        s2 = pd.Series(np.random.randn(24), index=idx)
        with tempfile.TemporaryDirectory() as td:
            compute_monthly_correlations({"A": s1, "B": s2}, Path(td), "test")
            # rebuild yearly for direct call
            df = pd.concat({"A": s1, "B": s2}, axis=1).dropna()
            yearly_rows = []
            for year, g in df.groupby(df.index.year):
                if len(g) >= 2:
                    c = g.corr()
                    c["year"] = year
                    c["n_months"] = len(g)
                    yearly_rows.append(c)
            yearly = pd.concat(yearly_rows)
            fig, ax = _plot_yearly_corr(yearly, Path(td) / "test.png", "test")
            self.assertEqual(len(ax.lines), 1)
            plt.close(fig)


class TestMissingData(unittest.TestCase):
    def _make_fake_tej(self, td: Path):
        a = Path(td) / "tej_a.txt"
        b = Path(td) / "tej_b.txt"
        a.write_text("dummy", encoding="utf-8")
        b.write_text("dummy", encoding="utf-8")
        return a, b

    def test_missing_industry_exits_nonzero_no_report(self):
        from research.strategy_combo import run_candidates
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            data = Path(td) / "data"
            data.mkdir()
            with patch.object(sys, "argv", [
                "run_candidates.py",
                "--out-dir", str(out),
                "--data-dir", str(data),
                "--industry-csv", str(Path(td)/"missing.csv")
            ]):
                with self.assertRaises(SystemExit) as cm:
                    run_candidates.main()
                self.assertNotEqual(cm.exception.code, 0)
            self.assertFalse((out / "report.md").exists())

    def test_etf_download_fail_exits_nonzero_no_report(self):
        from research.strategy_combo import run_candidates
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            data = Path(td) / "data"
            data.mkdir()
            tej_a, tej_b = self._make_fake_tej(td)
            ind_path = Path(td) / "industry.csv"
            ind_path.write_text("code,name,market,industry\n2330,台積電,上市,半導體業\n", encoding="utf-8")
            mem = pd.DataFrame({
                "code": ["2330"],
                "name": ["2330"],
                "start_date": pd.to_datetime("2010-01-01"),
                "end_date": pd.NaT,
            })
            call_count = {"n": 0}
            def fake_fetch(codes, ddir):
                call_count["n"] += 1
                if call_count["n"] == 2:
                    raise RuntimeError("etf fail")
                return {}
            fake_prices = {
                "2330": pd.Series(1.0, index=pd.bdate_range("2010-01-01", periods=2000)),
                "0050": pd.Series(1.0, index=pd.bdate_range("2010-01-01", periods=2000)),
                "00632R": pd.Series(1.0, index=pd.bdate_range("2010-01-01", periods=2000)),
            }
            stderr = io.StringIO()
            with patch.object(sys, "argv", [
                "run_candidates.py",
                "--out-dir", str(out),
                "--data-dir", str(data),
                "--industry-csv", str(ind_path),
            ]):
                with patch("research.strategy_combo.run_candidates.TEJ_PRICES_A", tej_a):
                    with patch("research.strategy_combo.run_candidates.TEJ_PRICES_B", tej_b):
                        with patch("research.strategy_combo.run_candidates.load_membership_intervals", return_value=mem):
                            with patch("research.strategy_combo.run_candidates.check_tej_files_exist"):
                                with patch("research.strategy_combo.run_candidates.load_nn3_monthly", return_value=pd.Series(1.0, index=pd.date_range("2015-01-31", periods=50, freq="ME"))):
                                    with patch("research.strategy_combo.run_candidates.load_twii", return_value=pd.DataFrame({"Close": pd.Series(1.0, index=pd.bdate_range("2010-01-01", periods=2000))})):
                                        with patch("research.strategy_combo.run_candidates.load_and_verify_tej_prices", return_value={}):
                                            with patch("research.strategy_combo.run_candidates.fetch_yfinance_prices", side_effect=fake_fetch) as mocked:
                                                with patch("research.strategy_combo.run_candidates.get_close_series", side_effect=lambda c, d: fake_prices.get(c, pd.Series())):
                                                    with patch("research.strategy_combo.run_candidates._count_dividends", return_value=0):
                                                        with contextlib.redirect_stderr(stderr):
                                                            with self.assertRaises(SystemExit) as cm:
                                                                run_candidates.main()
                                                            self.assertNotEqual(cm.exception.code, 0)
                                                            self.assertEqual(mocked.call_count, 2)
                                                            args = mocked.call_args_list[1][0][0]
                                                            self.assertIn("00679B", list(args))
            self.assertIn("ETF 價格下載失敗", stderr.getvalue())
            self.assertFalse((out / "report.md").exists())

    def test_dividend_fail_exits(self):
        from research.strategy_combo import run_candidates
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            data = Path(td) / "data"
            data.mkdir()
            tej_a, tej_b = self._make_fake_tej(td)
            ind_path = Path(td) / "industry.csv"
            ind_path.write_text("code,name,market,industry\n2330,台積電,上市,半導體業\n", encoding="utf-8")
            mem = pd.DataFrame({
                "code": ["2330"],
                "name": ["2330"],
                "start_date": pd.to_datetime("2010-01-01"),
                "end_date": pd.NaT,
            })
            # fake ETF caches
            for sym in ["0050.TW", "00679B.TWO", "00635U.TW"]:
                df = pd.DataFrame({"Close": [100.0, 101.0]}, index=pd.to_datetime(["2010-01-01", "2010-01-02"]))
                df.to_csv(data / f"{sym}.csv", encoding="utf-8")
            fake_prices = {
                "2330": pd.Series(1.0, index=pd.bdate_range("2010-01-01", periods=2000)),
                "0050": pd.Series(1.0, index=pd.bdate_range("2010-01-01", periods=2000)),
                "00632R": pd.Series(1.0, index=pd.bdate_range("2010-01-01", periods=2000)),
            }
            stderr = io.StringIO()
            with patch.object(sys, "argv", [
                "run_candidates.py",
                "--out-dir", str(out),
                "--data-dir", str(data),
                "--industry-csv", str(ind_path),
            ]):
                with patch("research.strategy_combo.run_candidates.TEJ_PRICES_A", tej_a):
                    with patch("research.strategy_combo.run_candidates.TEJ_PRICES_B", tej_b):
                        with patch("research.strategy_combo.run_candidates.load_membership_intervals", return_value=mem):
                            with patch("research.strategy_combo.run_candidates.check_tej_files_exist"):
                                with patch("research.strategy_combo.run_candidates.load_nn3_monthly", return_value=pd.Series(1.0, index=pd.date_range("2015-01-31", periods=50, freq="ME"))):
                                    with patch("research.strategy_combo.run_candidates.load_twii", return_value=pd.DataFrame({"Close": pd.Series(1.0, index=pd.bdate_range("2010-01-01", periods=2000))})):
                                        with patch("research.strategy_combo.run_candidates.load_and_verify_tej_prices", return_value={}):
                                            with patch("research.strategy_combo.run_candidates.fetch_yfinance_prices", return_value={}):
                                                with patch("research.strategy_combo.run_candidates.get_close_series", side_effect=lambda c, d: fake_prices.get(c, pd.Series())):
                                                    with patch("research.strategy_combo.run_candidates._count_dividends", side_effect=RuntimeError("div fail")):
                                                        with contextlib.redirect_stderr(stderr):
                                                            with self.assertRaises(SystemExit) as cm:
                                                                run_candidates.main()
                                                            self.assertNotEqual(cm.exception.code, 0)
            err = stderr.getvalue()
            self.assertIn("配息筆數取得失敗", err)
            self.assertTrue("0050" in err or "00679B" in err or "00635U" in err)
            self.assertFalse((out / "report.md").exists())


class TestSliceDaily(unittest.TestCase):
    def test_slice_includes_full_first_month(self):
        dates = pd.bdate_range("2015-05-01", "2015-07-31")
        s = pd.Series(1.0, index=dates)
        start_me = pd.Timestamp("2015-05-31")
        end_me = pd.Timestamp("2015-07-31")
        sliced = _slice_daily(s, start_me, end_me)
        self.assertEqual(sliced.index.min(), dates[0])
        self.assertLessEqual(sliced.index.max(), end_me)


class TestTurnoverAndMonths(unittest.TestCase):
    def test_avg_monthly_turnover(self):
        dates = pd.bdate_range("2020-01-01", periods=90)
        traded = pd.Series(0.0, index=dates)
        # one day in second month with 1.0
        m2 = dates[dates.to_period("M") == "2020-02"]
        traded.loc[m2[10]] = 1.0
        avg = _avg_monthly_turnover(traded, pd.Timestamp("2020-01-31"), pd.Timestamp("2020-03-31"))
        self.assertAlmostEqual(avg, 0.5 / 3, places=5)

    def test_months_inclusive(self):
        self.assertEqual(_months_inclusive(pd.Timestamp("2015-06-30"), pd.Timestamp("2026-08-31")), 135)
        self.assertEqual(_months_inclusive(pd.Timestamp("2015-05-31"), pd.Timestamp("2026-08-31")), 136)


if __name__ == "__main__":
    unittest.main()
