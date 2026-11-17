"""Report generation and plotting (AC-8, AC-9, AC-12)."""
from pathlib import Path
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd

from .metrics import monthly_metrics, daily_mdd_pct


def ensure_out(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)


def _df_to_markdown(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "_（無資料）_"
    headers = ["組合"] + list(df.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for idx, row in df.iterrows():
        cells = [str(idx)]
        for c in df.columns:
            v = row[c]
            cells.append(f"{v:.4f}" if isinstance(v, float) else str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def plot_equity_and_dd(series_dict: dict[str, pd.Series], out_dir: Path, prefix: str) -> None:
    ensure_out(out_dir)
    fig, ax = plt.subplots(figsize=(10, 5))
    for name, s in series_dict.items():
        s = s.dropna()
        if s.empty:
            continue
        eq = (1 + s).cumprod()
        ax.plot(eq.index, eq.values, label=name)
    ax.set_title(f"{prefix} Equity Curves")
    ax.legend()
    ax.grid(True)
    fig.savefig(out_dir / f"{prefix}_equity.png", dpi=120, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5))
    for name, s in series_dict.items():
        s = s.dropna()
        if s.empty:
            continue
        eq = (1 + s).cumprod()
        dd = eq / eq.cummax() - 1
        ax.plot(dd.index, dd.values * 100, label=name)
    ax.set_title(f"{prefix} Drawdowns (%)")
    ax.legend()
    ax.grid(True)
    fig.savefig(out_dir / f"{prefix}_drawdown.png", dpi=120, bbox_inches="tight")
    plt.close(fig)


def compute_correlations(
    nn3: pd.Series,
    a1: pd.Series,
    a2: pd.Series,
    b: pd.Series,
    out_dir: Path,
) -> dict:
    """Full-period, yearly and 36-month rolling (min_periods=36)."""
    ensure_out(out_dir)
    df = pd.concat({"NN3": nn3, "A1": a1, "A2": a2, "B": b}, axis=1, join="inner").dropna()

    full = df.corr()
    full.to_csv(out_dir / "corr_full.csv")

    yearly_rows = []
    for year, g in df.groupby(df.index.year):
        n = len(g)
        if n >= 2:
            c = g.corr()
            c["year"] = year
            c["n_months"] = n
            yearly_rows.append(c)
    yearly = pd.concat(yearly_rows) if yearly_rows else pd.DataFrame()
    if not yearly.empty:
        yearly.to_csv(out_dir / "corr_yearly.csv")

    roll = pd.DataFrame(index=df.index)
    for col in ["A1", "A2", "B"]:
        roll[f"{col}_NN3"] = df[col].rolling(36, min_periods=36).corr(df["NN3"])
    roll["A1_B"] = df["A1"].rolling(36, min_periods=36).corr(df["B"])
    roll["A2_B"] = df["A2"].rolling(36, min_periods=36).corr(df["B"])
    roll_valid = roll.dropna(how="all")
    n_valid_windows = len(roll_valid)
    roll_valid.to_csv(out_dir / "corr_rolling36.csv")

    fig, ax = plt.subplots(figsize=(10, 5))
    if n_valid_windows == 0:
        ax.text(0.5, 0.5, "樣本不足，未產出滾動相關", ha="center", va="center", fontsize=14)
        ax.set_axis_off()
    else:
        for c in roll.columns:
            ax.plot(roll.index, roll[c], label=c)
        ax.legend()
        ax.grid(True)
    ax.set_title("36-month Rolling Correlations")
    fig.savefig(out_dir / "corr_rolling36.png", dpi=120, bbox_inches="tight")
    plt.close(fig)

    return {"full": full, "yearly": yearly, "rolling": roll, "n_valid_windows": n_valid_windows}


def write_report(
    out_dir: Path,
    common_start: str,
    common_end: str,
    n_common_months: int,
    sample_ok: bool,
    nn3_full_metrics: dict,
    nn3_backup_metrics: dict,
    strategy_metrics: dict,
    scale_factors: dict,
    combo_summary: pd.DataFrame,
    data_notes: list[str],
    principal: float,
    coverage_rate: float,
    first_tradable: dict,
    never_tradable: dict,
    price_events: list,
    universe_csv: str,
    n_valid_windows: int = 0,
) -> None:
    ensure_out(out_dir)
    lines: list[str] = []
    lines.append("# 策略組合研究報告 (strategy_combo v5)\n")
    lines.append(f"產生時間：{datetime.now().strftime('%Y-%m-%d %H:%M')} 台北\n")

    lines.append("## 假設、資料來源與共同期間\n")
    lines.append(f"- 假設本金：{principal:,.0f} 新台幣。")
    lines.append("- 手續費 0.1425%（最低 20 元）、滑價每邊 0.1%。")
    lines.append("- 賣出證交稅：個股 0.3%；ETF（0050、00632R）0.1%（與系統 config 的 0.3% 不同）。")
    lines.append("- NN3 月報酬已含成本，不重算。")
    lines.append("- 價格：87 檔 + 0050 + 00632R 用 yfinance（auto_adjust=True）；6 檔（2311、2325、3474、3697、2823、2888）只用 TEJ 除權息調整，不混用。")
    lines.append("- 時點股票池：`inputs/tw50_membership_intervals.csv`（左閉右開）。")
    lines.append("- 加權指數：repo 內 snr_backtest/data/TWII.csv。")
    lines.append("- NN3：只讀 Desktop/trade_NN/out/portfolio_monthly.csv，主策略欄「Top20 等權 緩衝40 產業≤30%」。")
    for note in data_notes:
        lines.append(f"- {note}")
    lines.append("")
    lines.append(f"**共同期間**：{common_start} 至 {common_end}（終點為 NN3 最後一個月）。")
    lines.append("起點僅要求：NN3 有月報酬、加權指數 200 日均線已可計算、0050 與 00632R 皆有日價。")
    lines.append("不再要求 B 成分股完整歷史或可交易股票 ≥ 10 檔。")
    if not sample_ok:
        lines.append(f"**樣本不足**：共同期間完整月份數 {n_common_months} < 36。")
    else:
        lines.append(f"共同期間完整月份數：{n_common_months}。")
    lines.append(f"- 月底成分股／可交易檔數：見 `{universe_csv}`。")
    lines.append(f"- 價格覆蓋率：{coverage_rate:.2%}（詳見 out/price_coverage.csv；缺價日全部列出、不補值）。\n")

    lines.append("## 第一次可交易日與從未可交易原因\n")
    lines.append("可交易定義：當日是成分股、當日有收盤價、且含當日已有至少 200 個收盤價。")
    if first_tradable:
        lines.append("每一檔第一次可交易日：")
        for code, dt in sorted(first_tradable.items()):
            lines.append(f"- {code}: {pd.Timestamp(dt).date()}")
    if never_tradable:
        lines.append("共同期間內從未可交易者及原因：")
        for code, reason in sorted(never_tradable.items()):
            lines.append(f"- {code}: {reason}")
    lines.append("")

    if price_events:
        lines.append("## 價格中斷事件\n")
        for ev in price_events:
            last_d = pd.Timestamp(ev["last_price_date"]).date()
            orig = ev.get("original_sell_date")
            orig_s = pd.Timestamp(orig).date() if orig is not None else "（未排定）"
            lines.append(f"- {ev['code']}: 最後價格日 {last_d}，原定賣出日 {orig_s}")
        lines.append("")

    lines.append("## AC-2 NN3 基準核對（全期）\n")
    m = nn3_full_metrics
    lines.append(f"- 正式檔全期：Sharpe {m.get('sharpe', float('nan')):.4f}、MDD {m.get('mdd_pct', float('nan')):.4f}%、年化 {m.get('cagr_pct', float('nan')):.4f}%")
    lines.append("- 主管回報參考值：Sharpe 1.36±0.01、MDD −20.69%±0.1 個百分點、年化 31.26%±0.1 個百分點。")
    within = (
        abs(m.get("sharpe", 999) - 1.36) <= 0.01
        and abs(m.get("mdd_pct", 999) - (-20.69)) <= 0.1
        and abs(m.get("cagr_pct", 999) - 31.26) <= 0.1
    )
    lines.append(f"- 是否在容差內：{'是' if within else '否（已依 AC-2 在報告寫明，未改動原始數據）'}。")
    bm = nn3_backup_metrics
    lines.append(f"- 舊版備份對照：Sharpe {bm.get('sharpe', float('nan')):.4f}、MDD {bm.get('mdd_pct', float('nan')):.4f}%、年化 {bm.get('cagr_pct', float('nan')):.4f}%（僅對照）。\n")

    lines.append("## 各策略指標（共同期間）\n")
    lines.append("Sharpe 定義：月報酬的平均值除以標準差，再乘以 √12（無風險利率設為 0）。")
    lines.append("A、B 的日頻 MDD 僅供參考；含成本列使用含成本日序列，不含成本列使用不含成本日序列。\n")
    lines.append("| 策略 | 成本 | 年化報酬% | 年化波動% | Sharpe | 月頻MDD% | 日頻MDD% |")
    lines.append("|------|------|-----------|-----------|--------|----------|----------|")
    for name, mets in strategy_metrics.items():
        dmd = mets.get("daily_mdd")
        dmd_s = f"{dmd:.2f}" if isinstance(dmd, (int, float)) else ""
        cost_label = "含" if mets.get("with_cost") else "不含"
        lines.append(
            f"| {name} | {cost_label} | "
            f"{mets.get('cagr_pct', float('nan')):.2f} | {mets.get('ann_vol_pct', float('nan')):.2f} | "
            f"{mets.get('sharpe', float('nan')):.3f} | {mets.get('mdd_pct', float('nan')):.2f} | {dmd_s} |"
        )
    lines.append("")

    lines.append("## 相關係數（AC-9）\n")
    lines.append("滾動相關使用 min_periods=36（每個視窗必須滿 36 個月才計算，不足留空、不補值）。")
    lines.append(f"有效視窗數：{n_valid_windows}。")
    if n_valid_windows == 0:
        lines.append("樣本不足，未產出滾動相關。")
    lines.append("- out/corr_full.csv")
    lines.append("- out/corr_yearly.csv（當年月份 < 12 時含 n_months 欄）")
    lines.append("- out/corr_rolling36.csv 與 out/corr_rolling36.png\n")

    lines.append("## 風險縮放（AC-10）\n")
    lines.append("每個策略乘一個係數，使共同期間最大回撤等於 NN3 同期間最大回撤。")
    lines.append("**此係數使用全期（共同期間）資料計算，存在前視偏誤。**")
    for name, k in scale_factors.items():
        note = "（係數 > 1，融資或借券成本未計算）" if k > 1.0 else ""
        lines.append(f"- {name}: {k:.4f}{note}")
    lines.append("")

    lines.append("## 組合結果（AC-11）\n")
    lines.append("使用縮放後月報酬、每月再平衡。與「只用 NN3」並排。")
    if combo_summary is not None and not combo_summary.empty:
        lines.append(_df_to_markdown(combo_summary.round(4)))
        lines.append("")
        if "sharpe" in combo_summary.columns:
            lines.append(f"- Sharpe 最高：{combo_summary['sharpe'].idxmax()}")
        if "mdd_pct" in combo_summary.columns:
            lines.append(f"- 最大回撤最小：{combo_summary['mdd_pct'].idxmax()}")
    lines.append("")

    lines.append("## 圖表\n")
    lines.append("- 權益曲線與回撤：out/strategies_*.png、out/combos_*.png")
    lines.append("- 滾動相關：out/corr_rolling36.png\n")

    lines.append("## 安全與非目標\n")
    lines.append("- 不連任何券商介面、不讀寫交易紀錄或帳戶檔、不讀取環境變數或金鑰。")
    lines.append("- 不修改每日排程或儀表板。")
    lines.append("- 200 日均線與 B 參數皆固定，未做參數最佳化。\n")

    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
