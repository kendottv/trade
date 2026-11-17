"""One-command runner for strategy combination research (v5).

Usage (from repo root):
    python research/strategy_combo/run.py
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from research.strategy_combo.config import (  # noqa: E402
    DATA_DIR,
    DEFAULT_NN_OUT_DIR,
    DEFAULT_NN_BACKUP_DIR,
    DEFAULT_PRINCIPAL_TWD,
    TEJ_STOCK_CODES,
    ETF_CODES,
)
from research.strategy_combo.data import (  # noqa: E402
    load_nn3_monthly,
    load_twii,
    load_membership_intervals,
    constituents_on_date,
    check_tej_files_exist,
    load_and_verify_tej_prices,
    fetch_yfinance_prices,
    get_close_series,
)
from research.strategy_combo.strategies import (  # noqa: E402
    a1_monthly,
    a2_monthly,
    backtest_cta,
    backtest_b,
    compute_tradable_info,
)
from research.strategy_combo.metrics import monthly_metrics, daily_mdd_pct  # noqa: E402
from research.strategy_combo.scaling import scale_returns  # noqa: E402
from research.strategy_combo.portfolio import (  # noqa: E402
    equal_weight,
    two_strategy_scan,
    three_strategy_scan,
    summarize,
)
from research.strategy_combo.report import (  # noqa: E402
    plot_equity_and_dd,
    compute_correlations,
    write_report,
)


def _first_full_month(s: pd.Series, min_days: int = 15) -> pd.Timestamp | None:
    if s is None or s.empty:
        return None
    counts = s.resample("ME").count()
    valid = counts[counts >= min_days]
    return valid.index.min() if not valid.empty else None


def find_common_period(
    nn3: pd.Series,
    twii_close: pd.Series,
    p0050: pd.Series,
    p00632r: pd.Series,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """AC-3: start = first full month where NN3, TWII-200MA, 0050 and 00632R all ready.
    Does NOT look at B membership or B price starts.
    Returns month-end timestamps for the start and end months.
    """
    end = nn3.index.max()
    ma = twii_close.rolling(200, min_periods=200).mean()
    ma_ready = ma.first_valid_index()
    if ma_ready is None:
        raise RuntimeError("TWII 200-day MA never becomes available")

    # Adjust MA ready to first full month: if ready mid-month (after first trading day),
    # use the next month's end.
    ma_ready_period = ma_ready.to_period("M")
    month_begin = ma_ready_period.to_timestamp()
    first_td = twii_close.index[twii_close.index >= month_begin]
    first_td = first_td.min() if len(first_td) else None
    if first_td is not None and ma_ready > first_td:
        ma_full = (ma_ready_period + 1).to_timestamp("M")
    else:
        ma_full = ma_ready_period.to_timestamp("M")

    starts = [
        nn3.index.min(),
        ma_full,
        _first_full_month(p0050),
        _first_full_month(p00632r),
    ]
    start_candidates = [s for s in starts if s is not None]
    if not start_candidates:
        raise RuntimeError("Cannot determine common start")
    start = max(start_candidates)
    start = pd.Timestamp(start).to_period("M").to_timestamp("M")
    end = pd.Timestamp(end).to_period("M").to_timestamp("M")
    if start > end:
        raise RuntimeError(f"Common period empty: {start.date()} > {end.date()}")
    return start, end


def compute_month_end_universe(
    membership: pd.DataFrame,
    prices: dict[str, pd.Series],
    start: pd.Timestamp,
    end: pd.Timestamp,
    trading_dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Use last trading day of each month (from trading calendar)."""
    trading_dates = pd.DatetimeIndex(trading_dates).sort_values()
    months = pd.period_range(start, end, freq="M")
    rows = []
    for per in months:
        month_days = trading_dates[trading_dates.to_period("M") == per]
        if len(month_days) == 0:
            continue
        m = month_days.max()
        members = constituents_on_date(m, membership)
        n_trad = 0
        for c in members:
            ser = prices.get(c)
            if ser is not None and m in ser.index and int((ser.index <= m).sum()) >= 200:
                n_trad += 1
        rows.append({"month": str(per), "n_members": len(members), "n_tradable": n_trad})
    return pd.DataFrame(rows)


def compute_price_coverage(
    membership: pd.DataFrame,
    prices: dict[str, pd.Series],
    trading_dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    trading_dates = pd.DatetimeIndex(trading_dates).sort_values()
    rows = []
    for _, row in membership.iterrows():
        code = str(row["code"])
        start = pd.to_datetime(row["start_date"])
        end = pd.to_datetime(row["end_date"]) if pd.notna(row["end_date"]) else trading_dates.max() + pd.Timedelta(days=1)
        mask = (trading_dates >= start) & (trading_dates < end)
        expected_days = trading_dates[mask]
        ser = prices.get(code)
        if ser is None:
            actual = 0
            missing = expected_days
            source = "missing"
        else:
            have = expected_days.intersection(ser.index)
            actual = len(have)
            missing = expected_days.difference(ser.index)
            source = "tej" if code in TEJ_STOCK_CODES else "yfinance"
        missing_ranges = []
        if len(missing):
            missing = missing.sort_values()
            rng_start = missing[0]
            prev = missing[0]
            for d in missing[1:]:
                if (d - prev).days > 5:
                    missing_ranges.append(f"{rng_start.date()}~{prev.date()}")
                    rng_start = d
                prev = d
            missing_ranges.append(f"{rng_start.date()}~{prev.date()}")
        rows.append({
            "code": code,
            "source": source,
            "expected_days": len(expected_days),
            "actual_days": actual,
            "missing_ranges": "; ".join(missing_ranges) if missing_ranges else "",
        })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Strategy combo research runner (v5)")
    parser.add_argument("--nn-out-dir", type=Path, default=DEFAULT_NN_OUT_DIR)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent / "out")
    args = parser.parse_args()

    try:
        check_tej_files_exist()
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    out_dir: Path = args.out_dir
    data_dir: Path = args.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    fetch_date = datetime.now().strftime("%Y-%m-%d")
    data_notes = [f"yfinance 抓取／檢查日：{fetch_date}（period=max, auto_adjust=True）"]
    data_notes.append("TEJ 與 yfinance 調整方式可能不同（TEJ 為除權息調整，yfinance 為 auto_adjust）。")

    nn3_full = load_nn3_monthly(args.nn_out_dir)
    try:
        nn3_backup = load_nn3_monthly(DEFAULT_NN_BACKUP_DIR)
    except FileNotFoundError:
        nn3_backup = pd.Series(dtype=float, name="NN3_backup")

    twii = load_twii()
    twii_close = twii["Close"]
    membership = load_membership_intervals()

    tej_prices = load_and_verify_tej_prices()
    data_notes.append("TEJ 檔案已與 tej_manifest.csv 核對通過。")

    all_mem_codes = set(membership["code"].astype(str).unique())
    yf_codes = sorted(all_mem_codes - set(TEJ_STOCK_CODES))
    fetch_yfinance_prices(yf_codes + list(ETF_CODES), data_dir)

    prices: dict[str, pd.Series] = {}
    for code in yf_codes + list(ETF_CODES):
        try:
            prices[code] = get_close_series(code, data_dir)
            ser = prices[code]
            data_notes.append(f"{code} (yfinance): {ser.index.min().date()} 至 {ser.index.max().date()}")
        except FileNotFoundError:
            data_notes.append(f"{code}: yfinance 快取缺失")
    for code, ser in tej_prices.items():
        prices[code] = ser
        data_notes.append(f"{code} (TEJ): {ser.index.min().date()} 至 {ser.index.max().date()}")

    p0050 = prices.get("0050")
    p00632r = prices.get("00632R")
    if p0050 is None or p00632r is None:
        raise RuntimeError("0050 或 00632R 價格缺失")

    if "2330" not in prices:
        raise RuntimeError("2330 價格缺失，無法建立交易日曆")
    trading_dates = prices["2330"].index.sort_values()

    start, end = find_common_period(nn3_full, twii_close, p0050, p00632r)
    common_start = start.strftime("%Y-%m")
    common_end = end.strftime("%Y-%m")
    nn3 = nn3_full.loc[start:end].copy()
    n_common_months = len(nn3.dropna())
    sample_ok = n_common_months >= 36

    universe_df = compute_month_end_universe(membership, prices, start, end, trading_dates)
    universe_df.to_csv(out_dir / "month_end_universe.csv", index=False)

    coverage_df = compute_price_coverage(membership, prices, trading_dates)
    coverage_df.to_csv(out_dir / "price_coverage.csv", index=False)
    total_exp = coverage_df["expected_days"].sum()
    total_act = coverage_df["actual_days"].sum()
    coverage_rate = total_act / total_exp if total_exp else 0.0

    first_tradable, never_tradable = compute_tradable_info(prices, membership, trading_dates)

    daily_a1_nc = backtest_cta(twii_close, p0050, None, apply_costs=False, name="A1")
    daily_a1_c = backtest_cta(twii_close, p0050, None, apply_costs=True, name="A1")
    daily_a2_nc = backtest_cta(twii_close, p0050, p00632r, apply_costs=False, name="A2")
    daily_a2_c = backtest_cta(twii_close, p0050, p00632r, apply_costs=True, name="A2")

    # B covers the full first and last month of the common period
    # (from first trading day of start month through last trading day of end month)
    start_month_begin = start.to_period("M").to_timestamp()
    end_month_end = end.to_period("M").to_timestamp("M")
    b_dates = trading_dates[
        (trading_dates >= start_month_begin) & (trading_dates <= end_month_end)
    ]
    # Extend a few days past end so signals on the last trading day can fill,
    # but do not include those extra days in monthly returns or events.
    extra_fill_days = trading_dates[trading_dates > end_month_end][:3]
    b_dates_extended = b_dates.union(extra_fill_days)

    daily_b_nc, _ = backtest_b(prices, membership, b_dates_extended, apply_costs=False)
    daily_b_c, events_c = backtest_b(prices, membership, b_dates_extended, apply_costs=True)
    # Drop any events whose last_price_date is after the common-period end
    price_events = [
        ev for ev in events_c
        if pd.Timestamp(ev["last_price_date"]) <= end_month_end
    ]

    a1_nc = a1_monthly(twii_close, p0050, apply_costs=False).loc[start:end]
    a1_c = a1_monthly(twii_close, p0050, apply_costs=True).loc[start:end]
    a2_nc = a2_monthly(twii_close, p0050, p00632r, apply_costs=False).loc[start:end]
    a2_c = a2_monthly(twii_close, p0050, p00632r, apply_costs=True).loc[start:end]
    b_nc = ((1 + daily_b_nc).resample("ME").prod() - 1).loc[start:end]
    b_c = ((1 + daily_b_c).resample("ME").prod() - 1).loc[start:end]

    strategy_metrics = {}
    pairs = [
        ("A1_nocost", a1_nc, False, daily_a1_nc),
        ("A1_cost", a1_c, True, daily_a1_c),
        ("A2_nocost", a2_nc, False, daily_a2_nc),
        ("A2_cost", a2_c, True, daily_a2_c),
        ("B_nocost", b_nc, False, daily_b_nc),
        ("B_cost", b_c, True, daily_b_c),
        ("NN3", nn3, True, None),
    ]
    for label, series, with_cost, daily in pairs:
        m = monthly_metrics(series)
        m["with_cost"] = with_cost
        if daily is not None and not daily.empty:
            dslice = daily.loc[(daily.index >= start_month_begin) & (daily.index <= end_month_end)]
            m["daily_mdd"] = daily_mdd_pct(dslice)
        strategy_metrics[label] = m

    corr_result = compute_correlations(nn3, a1_c, a2_c, b_c, out_dir)
    n_valid_windows = corr_result.get("n_valid_windows", 0)

    target_mdd = monthly_metrics(nn3)["mdd_pct"]
    scaled = {"NN3": nn3}
    scale_factors = {}
    for name, s in [("A1", a1_c), ("A2", a2_c), ("B", b_c)]:
        sc, k = scale_returns(s, target_mdd)
        scaled[name] = sc
        scale_factors[name] = float(k)

    combos = {}
    combos["NN3+A1"] = equal_weight([scaled["NN3"], scaled["A1"]], "NN3+A1")
    combos["NN3+A2"] = equal_weight([scaled["NN3"], scaled["A2"]], "NN3+A2")
    combos["NN3+B"] = equal_weight([scaled["NN3"], scaled["B"]], "NN3+B")
    combos["NN3+A1+B"] = equal_weight([scaled["NN3"], scaled["A1"], scaled["B"]], "NN3+A1+B")
    combos["NN3+A2+B"] = equal_weight([scaled["NN3"], scaled["A2"], scaled["B"]], "NN3+A2+B")
    combos.update(two_strategy_scan(scaled["NN3"], scaled["A1"], "A1"))
    combos.update(two_strategy_scan(scaled["NN3"], scaled["A2"], "A2"))
    combos.update(two_strategy_scan(scaled["NN3"], scaled["B"], "B"))
    combos.update(three_strategy_scan(scaled["NN3"], scaled["A1"], scaled["B"], "A1"))
    combos.update(three_strategy_scan(scaled["NN3"], scaled["A2"], scaled["B"], "A2"))
    combos["NN3_only"] = scaled["NN3"]
    combo_summary = summarize(combos)
    combo_summary.to_csv(out_dir / "combo_summary.csv")

    plot_equity_and_dd({"NN3": nn3, "A1": a1_c, "A2": a2_c, "B": b_c}, out_dir, "strategies")
    plot_equity_and_dd(combos, out_dir, "combos")

    write_report(
        out_dir=out_dir,
        common_start=common_start,
        common_end=common_end,
        n_common_months=n_common_months,
        sample_ok=sample_ok,
        nn3_full_metrics=monthly_metrics(nn3_full),
        nn3_backup_metrics=monthly_metrics(nn3_backup.dropna()),
        strategy_metrics=strategy_metrics,
        scale_factors=scale_factors,
        combo_summary=combo_summary,
        data_notes=data_notes,
        principal=DEFAULT_PRINCIPAL_TWD,
        coverage_rate=coverage_rate,
        first_tradable=first_tradable,
        never_tradable=never_tradable,
        price_events=price_events,
        universe_csv="month_end_universe.csv",
        n_valid_windows=n_valid_windows,
    )
    print(f"Report written to {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
