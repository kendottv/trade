"""One-command runner for LV and XA candidate strategy research backtest.

Usage (from repo root):
    python research/strategy_combo/run_candidates.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from research.strategy_combo.config import (  # noqa: E402
    DATA_DIR,
    DEFAULT_NN_OUT_DIR,
    DEFAULT_PRINCIPAL_TWD,
    TEJ_STOCK_CODES,
    ETF_CODES,
    MEMBERSHIP_CSV,
    TEJ_PRICES_A,
    TEJ_PRICES_B,
)
from research.strategy_combo.data import (  # noqa: E402
    load_nn3_monthly,
    load_twii,
    load_membership_intervals,
    check_tej_files_exist,
    load_and_verify_tej_prices,
    fetch_yfinance_prices,
    get_close_series,
)
from research.strategy_combo.strategies import a1_monthly  # noqa: E402
from research.strategy_combo.metrics import monthly_metrics, daily_mdd_pct  # noqa: E402
from research.strategy_combo.scaling import scale_returns  # noqa: E402
from research.strategy_combo.lowvol import (  # noqa: E402
    load_industry_map,
    check_all_codes_have_industry,
    backtest_lowvol,
    compute_side_cost_03,
    WEIGHT_PER,
)
from research.strategy_combo.xamom import (  # noqa: E402
    filter_pre_listing,
    backtest_xa,
    a1_daily_03,
    a1_monthly_03,
)
from research.strategy_combo.candidates_report import (  # noqa: E402
    plot_equity_dd,
    compute_monthly_correlations,
    compute_daily_correlations,
    build_combo_table,
    write_candidates_report,
)
from research.strategy_combo.run import find_common_period  # noqa: E402


def _load_etf_universe(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"etf_universe.csv not found: {path}")
    return pd.read_csv(path, encoding="utf-8", parse_dates=["listing_date"])


def _sha256_file(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _count_dividends(yf_symbol: str) -> int:
    """Count dividend records from yfinance. Raise on failure."""
    import yfinance as yf
    t = yf.Ticker(yf_symbol)
    return len(t.dividends)


def _slice_daily(daily: pd.Series, start_month_end: pd.Timestamp, end_month_end: pd.Timestamp) -> pd.Series:
    """Slice daily series to full months: from first day of start month to end of end month."""
    if daily is None or daily.empty:
        return daily
    start_day = start_month_end.to_period("M").to_timestamp()
    end_day = end_month_end.to_period("M").to_timestamp("M")
    return daily.loc[(daily.index >= start_day) & (daily.index <= end_day)]


def _avg_monthly_turnover(traded: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> float:
    """Average of monthly (sum |traded_weight| / 2) over evaluation period."""
    if traded is None or traded.empty:
        return 0.0
    sliced = _slice_daily(traded, start, end)
    if sliced.empty:
        return 0.0
    monthly_sum = sliced.resample("ME").sum()
    monthly_to = monthly_sum / 2.0
    return float(monthly_to.mean()) if len(monthly_to) else 0.0


def _months_inclusive(start: pd.Timestamp, end: pd.Timestamp) -> int:
    """Number of months from start to end inclusive (both month-ends)."""
    return (end.to_period("M") - start.to_period("M")).n + 1


def _xa_holdings_rows(
    hold_xa: List[dict],
    xa_start_ts: pd.Timestamp,
    end: pd.Timestamp,
) -> List[dict]:
    """Build rows for xa_holdings.csv using month-period comparison (inclusive)."""
    rows: List[dict] = []
    if not hold_xa or xa_start_ts is None:
        return rows
    start_per = pd.Timestamp(xa_start_ts).to_period("M")
    end_per = pd.Timestamp(end).to_period("M")
    for h in hold_xa:
        d = pd.Timestamp(h["date"])
        if start_per <= d.to_period("M") <= end_per:
            etf_w = sum(h.get("weights", {}).values())
            cash_w = 1.0 - etf_w
            for code, w in h.get("weights", {}).items():
                rows.append({"date": d, "code": code, "weight": w})
            if cash_w > 1e-9:
                rows.append({"date": d, "code": "CASH", "weight": cash_w})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="LV + XA candidate strategies research runner")
    parser.add_argument("--nn-out-dir", type=Path, default=DEFAULT_NN_OUT_DIR)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent / "out" / "candidates")
    parser.add_argument("--industry-csv", type=Path, default=None)
    args = parser.parse_args()

    data_dir: Path = args.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    out_dir: Path = args.out_dir

    if args.industry_csv is None:
        industry_csv = _REPO_ROOT.parent / "trade_NN" / "data" / "industry.csv"
    else:
        industry_csv = args.industry_csv
    delisted_csv = Path(__file__).resolve().parent / "inputs" / "industry_delisted.csv"

    try:
        if not industry_csv.exists():
            print(f"industry.csv 不存在：{industry_csv}", file=sys.stderr)
            sys.exit(1)
        industry_map = load_industry_map(industry_csv, delisted_csv)
        industry_sha = _sha256_file(industry_csv)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    etf_path = Path(__file__).resolve().parent / "inputs" / "etf_universe.csv"
    try:
        etf_df = _load_etf_universe(etf_path)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    membership = load_membership_intervals()
    try:
        check_all_codes_have_industry(membership, industry_map)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    try:
        check_tej_files_exist()
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    tej_sha = []
    try:
        sha_a = _sha256_file(TEJ_PRICES_A)
        sha_b = _sha256_file(TEJ_PRICES_B)
        tej_sha.append(f"TEJ tej_prices_a.txt sha256: {sha_a}")
        tej_sha.append(f"TEJ tej_prices_b.txt sha256: {sha_b}")
    except Exception as e:
        print(f"TEJ sha256 計算失敗：{e}", file=sys.stderr)
        sys.exit(1)

    fetch_date = datetime.now().strftime("%Y-%m-%d")
    data_notes = [f"yfinance 抓取日：{fetch_date}（period=max, auto_adjust=True）"]
    data_notes.append(f"industry.csv sha256: {industry_sha}")

    nn3_full = load_nn3_monthly(args.nn_out_dir)
    twii = load_twii()
    twii_close = twii["Close"]

    tej_prices = load_and_verify_tej_prices()
    data_notes.append("TEJ 與 manifest 核對通過。")

    # LV + ETF_CODES prices
    all_mem_codes = set(membership["code"].astype(str).unique())
    yf_codes = sorted(all_mem_codes - set(TEJ_STOCK_CODES))
    try:
        fetch_yfinance_prices(yf_codes + list(ETF_CODES), data_dir)
    except RuntimeError as e:
        print(f"價格下載失敗：{e}", file=sys.stderr)
        sys.exit(1)

    prices: Dict[str, pd.Series] = {}
    for code in yf_codes + list(ETF_CODES):
        try:
            prices[code] = get_close_series(code, data_dir)
        except FileNotFoundError:
            print(f"{code} 價格缺失", file=sys.stderr)
            sys.exit(1)
    for code, ser in tej_prices.items():
        prices[code] = ser

    p0050 = prices.get("0050")
    p00632r = prices.get("00632R")
    if p0050 is None or p00632r is None:
        print("0050 或 00632R 價格缺失", file=sys.stderr)
        sys.exit(1)
    if "2330" not in prices:
        print("2330 價格缺失，無法建立交易日曆", file=sys.stderr)
        sys.exit(1)
    trading_dates = prices["2330"].index.sort_values()

    # ETF prices for XA
    etf_codes = etf_df["code"].astype(str).tolist()
    etf_listing = dict(zip(etf_df["code"].astype(str), etf_df["listing_date"]))
    etf_yf = dict(zip(etf_df["code"].astype(str), etf_df["yf_symbol"].astype(str)))
    try:
        fetch_yfinance_prices(etf_codes, data_dir)
    except RuntimeError as e:
        print(f"ETF 價格下載失敗：{e}", file=sys.stderr)
        sys.exit(1)

    etf_prices: Dict[str, pd.Series] = {}
    etf_coverage_rows = []
    for _, row in etf_df.iterrows():
        code = str(row["code"])
        yf_sym = str(row["yf_symbol"])
        listing = pd.Timestamp(row["listing_date"])
        found = None
        for suf in (".TW", ".TWO"):
            p = data_dir / f"{code}{suf}.csv"
            if p.exists():
                found = f"{code}{suf}"
                break
        if found != yf_sym:
            print(f"ETF {code} 快取檔名 {found} 與 etf_universe.csv 的 {yf_sym} 不一致", file=sys.stderr)
            sys.exit(1)
        try:
            raw = pd.read_csv(data_dir / f"{yf_sym}.csv", index_col=0, parse_dates=True, encoding="utf-8")
            yf_first = raw.index.min().date() if not raw.empty else None
            filtered, n_drop = filter_pre_listing(raw, listing)
            col = "Close" if "Close" in filtered.columns else filtered.columns[0]
            etf_prices[code] = filtered[col].sort_index()
            try:
                n_div = _count_dividends(yf_sym)
            except Exception as e:
                print(f"ETF {code} 配息筆數取得失敗：{e}", file=sys.stderr)
                sys.exit(1)
            etf_coverage_rows.append({
                "code": code,
                "yf_symbol": yf_sym,
                "listing_date": listing.date(),
                "yf_first": yf_first,
                "filtered_first": filtered.index.min().date() if not filtered.empty else None,
                "n_dropped_pre_listing": n_drop,
                "n_dividends_yf": n_div,
            })
            data_notes.append(f"{code}: yfinance 最早 {yf_first}，剔除上市前 {n_drop} 筆")
        except Exception as e:
            print(f"ETF {code} 處理失敗：{e}", file=sys.stderr)
            sys.exit(1)

    etf_coverage = pd.DataFrame(etf_coverage_rows)

    # now safe to create out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    etf_coverage.to_csv(out_dir / "etf_coverage.csv", index=False, encoding="utf-8")

    # common period for LV (same as v5)
    start, end = find_common_period(nn3_full, twii_close, p0050, p00632r)
    v5_n = _months_inclusive(start, end)
    lv_start = start.strftime("%Y-%m")
    lv_end = end.strftime("%Y-%m")
    nn3_lv = nn3_full.loc[start:end].copy()
    lv_n_nn3 = len(nn3_lv.dropna())

    # LV backtest
    daily_lv_nc, monthly_lv_nc, hold_lv_nc, _, traded_lv_nc = backtest_lowvol(
        prices, membership, industry_map, trading_dates, apply_costs=False
    )
    daily_lv_c, monthly_lv_c, hold_lv_c, events_lv, traded_lv_c = backtest_lowvol(
        prices, membership, industry_map, trading_dates, apply_costs=True
    )
    monthly_lv_nc = monthly_lv_nc.loc[start:end]
    monthly_lv_c = monthly_lv_c.loc[start:end]
    lv_n = len(monthly_lv_c.dropna())
    if lv_n != v5_n:
        print(f"LV 月數 {lv_n} 與 v5 月數 {v5_n} 不符", file=sys.stderr)
        sys.exit(1)

    daily_lv_c_slice = _slice_daily(daily_lv_c, start, end)
    daily_lv_nc_slice = _slice_daily(daily_lv_nc, start, end)

    # XA
    xa_daily_nc, xa_monthly_nc, hold_xa_nc, hold_months_nc, first_perf, traded_xa_nc = backtest_xa(
        etf_prices, etf_listing, trading_dates, apply_costs=False, end_limit=end
    )
    xa_daily_c, xa_monthly_c, hold_xa_c, hold_months, first_perf_c, traded_xa_c = backtest_xa(
        etf_prices, etf_listing, trading_dates, apply_costs=True, end_limit=end
    )
    if first_perf is None or xa_monthly_c.empty:
        xa_start_ts = end
        xa_n = 0
        xa_start = "N/A"
    else:
        xa_start_ts = first_perf
        xa_monthly_c = xa_monthly_c.loc[:end]
        xa_n = len(xa_monthly_c.dropna())
        xa_start = xa_start_ts.strftime("%Y-%m")
    xa_end = end.strftime("%Y-%m")
    nn3_xa = nn3_full.loc[xa_start_ts:end].copy() if xa_n else pd.Series(dtype=float)

    # A1 0.3% daily + monthly and 0.1%
    daily_a1_03 = a1_daily_03(twii_close, p0050, apply_costs=True)
    a1_03 = a1_monthly_03(twii_close, p0050, apply_costs=True).loc[start:end]
    a1_01 = a1_monthly(twii_close, p0050, apply_costs=True).loc[start:end]
    a1_03_xa = a1_monthly_03(twii_close, p0050, apply_costs=True).loc[xa_start_ts:end] if xa_n else pd.Series(dtype=float)
    a1_01_xa = a1_monthly(twii_close, p0050, apply_costs=True).loc[xa_start_ts:end] if xa_n else pd.Series(dtype=float)
    daily_a1_03_lv = _slice_daily(daily_a1_03, start, end)
    daily_a1_03_xa = _slice_daily(daily_a1_03, xa_start_ts, end) if xa_n else pd.Series(dtype=float)

    # metrics
    def _m(s, daily=None, period="", with_cost=True, extra=None):
        m = monthly_metrics(s)
        m["period"] = period
        m["with_cost"] = with_cost
        if daily is not None and not daily.empty:
            m["daily_mdd"] = daily_mdd_pct(daily)
        if extra:
            m.update(extra)
        return m

    # average holdings: once per month, last trading day before rebalance (month-end)
    # period comparison so calendar month-end not being a trading day does not drop the month
    def _avg_holdings(holds, start_m, end_m):
        if not holds:
            return 0.0
        counts = []
        start_per = pd.Timestamp(start_m).to_period("M")
        end_per = pd.Timestamp(end_m).to_period("M")
        for h in holds:
            d = pd.Timestamp(h["date"])
            if start_per <= d.to_period("M") <= end_per:
                counts.append(h.get("n", 0))
        return float(np.mean(counts)) if counts else 0.0

    lv_avg_n = _avg_holdings(hold_lv_c, start, end)
    xa_avg_n = _avg_holdings(hold_xa_c, xa_start_ts, end) if xa_n else 0.0
    lv_turn = _avg_monthly_turnover(traded_lv_c, start, end)
    xa_turn = _avg_monthly_turnover(traded_xa_c, xa_start_ts, end) if xa_n else 0.0

    metrics = {
        "LV_nocost": _m(monthly_lv_nc, daily_lv_nc_slice, "LV", False, {"avg_n": lv_avg_n, "avg_turnover": lv_turn}),
        "LV_cost": _m(monthly_lv_c, daily_lv_c_slice, "LV", True, {"avg_n": lv_avg_n, "avg_turnover": lv_turn}),
        "XA_nocost": _m(xa_monthly_nc.loc[xa_start_ts:end] if xa_n else pd.Series(), _slice_daily(xa_daily_nc, xa_start_ts, end) if xa_n else None, "XA", False, {"avg_n": xa_avg_n, "avg_turnover": xa_turn}),
        "XA_cost": _m(xa_monthly_c if xa_n else pd.Series(), _slice_daily(xa_daily_c, xa_start_ts, end) if xa_n else None, "XA", True, {"avg_n": xa_avg_n, "avg_turnover": xa_turn}),
        "NN3_LV": _m(nn3_lv, None, "LV", True),
        "A1_03_LV": _m(a1_03, daily_a1_03_lv, "LV", True),
        "A1_01_LV": _m(a1_01, None, "LV", True),
        "NN3_XA": _m(nn3_xa, None, "XA", True) if xa_n else {},
        "A1_03_XA": _m(a1_03_xa, daily_a1_03_xa, "XA", True) if xa_n else {},
        "A1_01_XA": _m(a1_01_xa, None, "XA", True) if xa_n else {},
    }

    # scaled
    target_mdd_lv = monthly_metrics(nn3_lv)["mdd_pct"]
    target_mdd_xa = monthly_metrics(nn3_xa)["mdd_pct"] if xa_n else np.nan
    scale_factors = {}
    scaled_lv = {}
    for name, s in [("LV", monthly_lv_c), ("A1", a1_03)]:
        sc, k = scale_returns(s, target_mdd_lv)
        scaled_lv[name] = sc
        scale_factors[f"{name}_LV"] = float(k)
    scaled_xa = {}
    if xa_n:
        for name, s in [("XA", xa_monthly_c), ("A1", a1_03_xa)]:
            sc, k = scale_returns(s, target_mdd_xa)
            scaled_xa[name] = sc
            scale_factors[f"{name}_XA"] = float(k)

    # scaled comparison table
    scaled_rows = []
    for period, nn3s, a1s, news, scales in [
        ("LV", nn3_lv, a1_03, monthly_lv_c, scaled_lv),
        ("XA", nn3_xa, a1_03_xa, xa_monthly_c if xa_n else pd.Series(), scaled_xa),
    ]:
        if period == "XA" and not xa_n:
            continue
        for label, ser, scaled in [
            ("NN3", nn3s, None),
            ("A1", a1s, scales.get("A1")),
            ("NEW", news, scales.get(period if period == "LV" else "XA")),
        ]:
            m = monthly_metrics(ser)
            row = {"item": f"{period}_{label}", "cagr_pct": m["cagr_pct"], "sharpe": m["sharpe"], "mdd_pct": m["mdd_pct"], "scale": 1.0}
            if scaled is not None:
                ms = monthly_metrics(scaled)
                row["scaled_cagr_pct"] = ms["cagr_pct"]
                row["scaled_sharpe"] = ms["sharpe"]
                row["scaled_mdd_pct"] = ms["mdd_pct"]
                row["scale"] = scale_factors.get(f"{label}_{period}" if label != "NEW" else f"{'LV' if period=='LV' else 'XA'}_{period}", 1)
            scaled_rows.append(row)
    scaled_comparison = pd.DataFrame(scaled_rows).set_index("item")

    # correlations
    corr_notes = []
    m_series_lv = {"LV": monthly_lv_c, "NN3": nn3_lv, "A1": a1_03}
    res = compute_monthly_correlations(m_series_lv, out_dir, "lv")
    corr_notes.append(f"LV 月報酬相關有效視窗數：{res.get('n_valid_windows', 0)}")
    if res.get("n_valid_windows", 0) == 0:
        corr_notes.append("LV 月報酬滾動相關樣本不足")
    if xa_n:
        m_series_xa = {"XA": xa_monthly_c, "NN3": nn3_xa, "A1": a1_03_xa}
        res = compute_monthly_correlations(m_series_xa, out_dir, "xa")
        corr_notes.append(f"XA 月報酬相關有效視窗數：{res.get('n_valid_windows', 0)}")
        if res.get("n_valid_windows", 0) == 0:
            corr_notes.append("XA 月報酬滾動相關樣本不足")
        m_series_lvxa = {"LV": monthly_lv_c.loc[xa_start_ts:end], "XA": xa_monthly_c}
        res = compute_monthly_correlations(m_series_lvxa, out_dir, "lvxa")
        corr_notes.append(f"LV-XA 月報酬相關有效視窗數：{res.get('n_valid_windows', 0)}")
        if res.get("n_valid_windows", 0) == 0:
            corr_notes.append("LV-XA 月報酬滾動相關樣本不足")
    d_lv = daily_lv_c_slice
    d_xa = _slice_daily(xa_daily_c, xa_start_ts, end) if xa_n else pd.Series(dtype=float)
    d_a1 = daily_a1_03_lv
    res = compute_daily_correlations({"LV": d_lv, "A1": d_a1}, out_dir, "daily_lv")
    corr_notes.append(f"LV-A1 日相關有效視窗數：{res.get('n_valid_windows', 0)}")
    if res.get("n_valid_windows", 0) == 0:
        corr_notes.append("LV-A1 日相關樣本不足")
    if xa_n:
        res = compute_daily_correlations({"XA": d_xa, "A1": daily_a1_03_xa}, out_dir, "daily_xa")
        corr_notes.append(f"XA-A1 日相關有效視窗數：{res.get('n_valid_windows', 0)}")
        if res.get("n_valid_windows", 0) == 0:
            corr_notes.append("XA-A1 日相關樣本不足")
        res = compute_daily_correlations({"LV": _slice_daily(daily_lv_c, xa_start_ts, end), "XA": d_xa}, out_dir, "daily_lvxa")
        corr_notes.append(f"LV-XA 日相關有效視窗數：{res.get('n_valid_windows', 0)}")
        if res.get("n_valid_windows", 0) == 0:
            corr_notes.append("LV-XA 日相關樣本不足")
    corr_notes.append("日頻相關裡沒有 NN3")

    # combos
    try:
        combo_lv = build_combo_table(nn3_lv, a1_03, monthly_lv_c, label="LV", expected_months=lv_n)
        combo_add = combo_lv
        if xa_n:
            combo_xa = build_combo_table(nn3_xa, a1_03_xa, xa_monthly_c, label="XA", expected_months=xa_n)
            combo_add = pd.concat([combo_lv, combo_xa])
    except Exception as e:
        print(f"組合對齊失敗：{e}", file=sys.stderr)
        sys.exit(1)
    combo_add.to_csv(out_dir / "combo_add.csv", encoding="utf-8")

    try:
        combo_lv_s = build_combo_table(nn3_lv, scaled_lv.get("A1", a1_03), scaled_lv.get("LV", monthly_lv_c), label="LV_scaled", expected_months=lv_n)
        combo_add_scaled = combo_lv_s
        if xa_n and "XA" in scaled_xa:
            combo_xa_s = build_combo_table(nn3_xa, scaled_xa.get("A1", a1_03_xa), scaled_xa["XA"], label="XA_scaled", expected_months=xa_n)
            combo_add_scaled = pd.concat([combo_lv_s, combo_xa_s])
    except Exception as e:
        print(f"縮放組合對齊失敗：{e}", file=sys.stderr)
        sys.exit(1)
    combo_add_scaled.to_csv(out_dir / "combo_add_scaled.csv", encoding="utf-8")

    # holdings CSVs: only evaluation period, once per month (month-end)
    if hold_lv_c:
        rows = []
        for h in hold_lv_c:
            d = pd.Timestamp(h["date"])
            if start <= d <= end:
                for code in h.get("codes", []):
                    rows.append({"date": d, "code": code, "weight": h["weights"].get(code, 0), "industry": industry_map.get(code, "")})
        pd.DataFrame(rows).to_csv(out_dir / "lv_holdings.csv", index=False, encoding="utf-8")
    if hold_xa_c and xa_n:
        rows = _xa_holdings_rows(hold_xa_c, xa_start_ts, end)
        pd.DataFrame(rows).to_csv(out_dir / "xa_holdings.csv", index=False, encoding="utf-8")

    # series CSVs (period only)
    monthly_lv_c.to_csv(out_dir / "lv_monthly.csv", encoding="utf-8")
    if xa_n:
        xa_monthly_c.to_csv(out_dir / "xa_monthly.csv", encoding="utf-8")
        _slice_daily(xa_daily_c, xa_start_ts, end).to_csv(out_dir / "xa_daily.csv", encoding="utf-8")
    daily_lv_c_slice.to_csv(out_dir / "lv_daily.csv", encoding="utf-8")

    # metrics csv
    met_rows = []
    for k, v in metrics.items():
        if v:
            row = {"name": k}
            row.update({kk: vv for kk, vv in v.items() if not isinstance(vv, (dict, list))})
            met_rows.append(row)
    pd.DataFrame(met_rows).to_csv(out_dir / "metrics.csv", index=False, encoding="utf-8")

    # scaled metrics
    scaled_met_rows = []
    for name, s in scaled_lv.items():
        m = monthly_metrics(s)
        m["name"] = f"{name}_scaled_LV"
        m["scale"] = scale_factors.get(f"{name}_LV", 1)
        scaled_met_rows.append(m)
    if xa_n:
        for name, s in scaled_xa.items():
            m = monthly_metrics(s)
            m["name"] = f"{name}_scaled_XA"
            m["scale"] = scale_factors.get(f"{name}_XA", 1)
            scaled_met_rows.append(m)
    pd.DataFrame(scaled_met_rows).to_csv(out_dir / "scaled_metrics.csv", index=False, encoding="utf-8")

    # plots
    plot_equity_dd({"LV": monthly_lv_c, "NN3": nn3_lv, "A1": a1_03}, out_dir, "lv")
    if xa_n:
        plot_equity_dd({"XA": xa_monthly_c, "NN3": nn3_xa, "A1": a1_03_xa}, out_dir, "xa")

    assumptions = [
        "LV：每月最後交易日 t 算訊號，t+1 收盤成交；波動 = 過去 250 日報酬標準差（ddof=1）；取最低 10 檔，每檔權重 10%，產業上限 30%，不足放現金。",
        "XA：3/6/12 個月總報酬平均（月底價取最後交易日）；取前 2 名各 50%；動能 ≤ 0 改持現金（報酬 0）。",
        "換倉只買賣變動部分；強制賣出後現金至下次調倉。",
        "A1 用 0.3% 稅重算；報告另附 v5 0.1% 數字。",
        "NN3 沿用原月報酬（已含成本）。",
        "平均每月換手率 = 評估期間內每月（交易權重絕對值總和 ÷ 2）的平均，含強制賣出。",
    ]

    turnover_notes = [
        f"LV 平均持股檔數：{lv_avg_n:.2f}，平均每月換手率：{lv_turn:.4f}",
        f"XA 平均持股檔數：{xa_avg_n:.2f}，平均每月換手率：{xa_turn:.4f}",
        f"XA 持有月數（XA 段內）：{hold_months}",
    ]

    sample_insufficient = lv_n < 36 or xa_n < 36

    write_candidates_report(
        out_dir=out_dir,
        assumptions=assumptions,
        lv_period=(lv_start, lv_end, lv_n),
        xa_period=(xa_start, xa_end, xa_n),
        v5_n=v5_n,
        metrics=metrics,
        scale_factors=scale_factors,
        scaled_comparison=scaled_comparison,
        combo_add=combo_add,
        combo_add_scaled=combo_add_scaled,
        corr_notes=corr_notes,
        etf_coverage=etf_coverage,
        data_notes=data_notes,
        principal=DEFAULT_PRINCIPAL_TWD,
        turnover_notes=turnover_notes,
        sample_insufficient=sample_insufficient,
        tej_sha=tej_sha,
    )
    print(f"Candidates report written to {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
