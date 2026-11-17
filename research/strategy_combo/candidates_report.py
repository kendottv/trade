"""Report, metrics, correlations and plots for LV / XA candidates."""
from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from research.strategy_combo.metrics import monthly_metrics, daily_mdd_pct
from research.strategy_combo.scaling import scale_returns


def ensure_out(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)


def _md_table(df: pd.DataFrame, index_name: str = "") -> str:
    if df is None or df.empty:
        return "_（無資料）_"
    headers = [index_name] + list(df.columns) if index_name else list(df.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for idx, row in df.iterrows():
        cells = [str(idx)] if index_name else []
        for c in df.columns:
            v = row[c]
            if isinstance(v, float):
                cells.append(f"{v:.4f}" if not np.isnan(v) else "")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def plot_equity_dd(series_dict: Dict[str, pd.Series], out_dir: Path, prefix: str) -> None:
    ensure_out(out_dir)
    fig, ax = plt.subplots(figsize=(10, 5))
    for name, s in series_dict.items():
        s = s.dropna()
        if s.empty:
            continue
        eq = (1 + s).cumprod()
        ax.plot(eq.index, eq.values, label=name)
    ax.set_title(f"{prefix} Equity")
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
    ax.set_title(f"{prefix} Drawdown %")
    ax.legend()
    ax.grid(True)
    fig.savefig(out_dir / f"{prefix}_drawdown.png", dpi=120, bbox_inches="tight")
    plt.close(fig)


def _plot_yearly_corr(yearly: pd.DataFrame, out_path: Path, title: str) -> Tuple[plt.Figure, plt.Axes]:
    """Plot one line per pair. Return fig, ax for testing."""
    fig, ax = plt.subplots(figsize=(10, 5))
    if yearly.empty or "year" not in yearly.columns:
        ax.text(0.5, 0.5, "insufficient sample", ha="center", va="center")
        ax.set_axis_off()
    else:
        pairs_plotted = 0
        cols = [c for c in yearly.columns if c not in ("year", "n_months")]
        years = sorted(yearly["year"].unique()) if "year" in yearly.columns else []
        for c1_idx, c1 in enumerate(cols):
            for c2 in cols[c1_idx + 1:]:
                ys = []
                xs = []
                for y in years:
                    sub = yearly[(yearly["year"] == y)]
                    if c1 in sub.index and c2 in sub.columns:
                        val = sub.loc[c1, c2] if c1 in sub.index else np.nan
                        if pd.notna(val):
                            xs.append(y)
                            ys.append(val)
                if xs:
                    ax.plot(xs, ys, label=f"{c1}-{c2}")
                    pairs_plotted += 1
        if pairs_plotted == 0:
            ax.text(0.5, 0.5, "insufficient sample", ha="center", va="center")
            ax.set_axis_off()
        else:
            ax.legend()
            ax.grid(True)
    ax.set_title(title)
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    return fig, ax


def compute_monthly_correlations(
    series_dict: Dict[str, pd.Series],
    out_dir: Path,
    prefix: str,
) -> Dict:
    """Full, yearly, 36-month rolling (min_periods=36). Keep NaN rows."""
    ensure_out(out_dir)
    df = pd.concat(series_dict, axis=1, join="inner").dropna()
    if df.empty:
        return {"n_valid_windows": 0}

    full = df.corr()
    full.to_csv(out_dir / f"corr_{prefix}_monthly_full.csv", encoding="utf-8")

    # full heatmap
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(full.values, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(full.columns)))
    ax.set_yticks(range(len(full.index)))
    ax.set_xticklabels(full.columns)
    ax.set_yticklabels(full.index)
    plt.colorbar(im, ax=ax)
    ax.set_title(f"{prefix} full corr")
    fig.savefig(out_dir / f"corr_{prefix}_monthly_full.png", dpi=120, bbox_inches="tight")
    plt.close(fig)

    yearly_rows = []
    for year, g in df.groupby(df.index.year):
        if len(g) >= 2:
            c = g.corr()
            c["year"] = year
            c["n_months"] = len(g)
            yearly_rows.append(c)
    if yearly_rows:
        yearly = pd.concat(yearly_rows)
        yearly.to_csv(out_dir / f"corr_{prefix}_monthly_yearly.csv", encoding="utf-8")
        fig, ax = _plot_yearly_corr(yearly, out_dir / f"corr_{prefix}_monthly_yearly.png", f"{prefix} yearly corr")
        plt.close(fig)
    else:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "insufficient sample", ha="center", va="center")
        ax.set_axis_off()
        fig.savefig(out_dir / f"corr_{prefix}_monthly_yearly.png", dpi=120, bbox_inches="tight")
        plt.close(fig)

    roll = pd.DataFrame(index=df.index)
    cols = list(df.columns)
    for i, c1 in enumerate(cols):
        for c2 in cols[i + 1:]:
            roll[f"{c1}_{c2}"] = df[c1].rolling(36, min_periods=36).corr(df[c2])
    # keep all rows, NaN stay NaN
    roll.to_csv(out_dir / f"corr_{prefix}_monthly_rolling36.csv", encoding="utf-8", na_rep="")
    n_valid = int(roll.notna().any(axis=1).sum())

    fig, ax = plt.subplots(figsize=(10, 5))
    if n_valid == 0:
        ax.text(0.5, 0.5, "insufficient sample", ha="center", va="center")
        ax.set_axis_off()
    else:
        for c in roll.columns:
            ax.plot(roll.index, roll[c], label=c)
        ax.legend()
        ax.grid(True)
    ax.set_title(f"{prefix} 36m Rolling Corr")
    fig.savefig(out_dir / f"corr_{prefix}_monthly_rolling36.png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return {"n_valid_windows": n_valid}


def compute_daily_correlations(
    series_dict: Dict[str, pd.Series],
    out_dir: Path,
    prefix: str = "daily",
) -> Dict:
    """Full and 250-day rolling (min_periods=250). No NN3 allowed."""
    if any("NN3" in k.upper() for k in series_dict):
        raise ValueError("Daily correlations must not include NN3")
    ensure_out(out_dir)
    df = pd.concat(series_dict, axis=1, join="inner").dropna()
    if df.empty:
        return {"n_valid_windows": 0}
    full = df.corr()
    full.to_csv(out_dir / f"corr_{prefix}_full.csv", encoding="utf-8")

    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(full.values, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(full.columns)))
    ax.set_yticks(range(len(full.index)))
    ax.set_xticklabels(full.columns)
    ax.set_yticklabels(full.index)
    plt.colorbar(im, ax=ax)
    ax.set_title(f"{prefix} full corr")
    fig.savefig(out_dir / f"corr_{prefix}_full.png", dpi=120, bbox_inches="tight")
    plt.close(fig)

    roll = pd.DataFrame(index=df.index)
    cols = list(df.columns)
    for i, c1 in enumerate(cols):
        for c2 in cols[i + 1:]:
            roll[f"{c1}_{c2}"] = df[c1].rolling(250, min_periods=250).corr(df[c2])
    roll.to_csv(out_dir / f"corr_{prefix}_rolling250.csv", encoding="utf-8", na_rep="")
    n_valid = int(roll.notna().any(axis=1).sum())

    fig, ax = plt.subplots(figsize=(10, 5))
    if n_valid == 0:
        ax.text(0.5, 0.5, "insufficient sample", ha="center", va="center")
        ax.set_axis_off()
    else:
        for c in roll.columns:
            ax.plot(roll.index, roll[c], label=c)
        ax.legend()
        ax.grid(True)
    ax.set_title(f"{prefix} 250d Rolling Corr")
    fig.savefig(out_dir / f"corr_{prefix}_rolling250.png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return {"n_valid_windows": n_valid}


def build_combo_table(
    nn3: pd.Series,
    a1: pd.Series,
    new: pd.Series,
    weights: Tuple[float, ...] = (0.10, 0.20, 0.33),
    label: str = "NEW",
    base_weights: Tuple[float, float] = (0.6, 0.4),
    expected_months: Optional[int] = None,
) -> pd.DataFrame:
    """Inner-join, dropna, check weight sum=1, return baseline + new combos with diffs."""
    bw1, bw2 = base_weights
    if abs(bw1 + bw2 - 1.0) > 1e-9:
        raise ValueError(f"base weights sum not 1: {base_weights}")
    for w in weights:
        if not (0 < w < 1):
            raise ValueError(f"weight {w} not in (0, 1)")
        total = (1 - w) * bw1 + (1 - w) * bw2 + w
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"combo weight sum not 1 for w={w}")
    df = pd.concat({"NN3": nn3, "A1": a1, "NEW": new}, axis=1, join="inner").dropna()
    if expected_months is not None and len(df) < expected_months:
        raise RuntimeError(f"aligned months {len(df)} < expected {expected_months}")
    if df.empty:
        raise RuntimeError("combo alignment produced empty series")
    base = bw1 * df["NN3"] + bw2 * df["A1"]
    rows = []
    m = monthly_metrics(base)
    rows.append({
        "name": f"baseline_{label}",
        "cagr_pct": m["cagr_pct"],
        "sharpe": m["sharpe"],
        "mdd_pct": m["mdd_pct"],
        "sharpe_diff": 0.0,
        "mdd_diff_pp": 0.0,
    })
    for w in weights:
        combo = (1 - w) * base + w * df["NEW"]
        m = monthly_metrics(combo)
        rows.append({
            "name": f"{label}_{int(w*100)}",
            "cagr_pct": m["cagr_pct"],
            "sharpe": m["sharpe"],
            "mdd_pct": m["mdd_pct"],
            "sharpe_diff": m["sharpe"] - rows[0]["sharpe"],
            "mdd_diff_pp": m["mdd_pct"] - rows[0]["mdd_pct"],
        })
    return pd.DataFrame(rows).set_index("name")


def write_candidates_report(
    out_dir: Path,
    assumptions: List[str],
    lv_period: Tuple[str, str, int],
    xa_period: Tuple[str, str, int],
    v5_n: int,
    metrics: Dict[str, dict],
    scale_factors: Dict[str, float],
    scaled_comparison: pd.DataFrame,
    combo_add: pd.DataFrame,
    combo_add_scaled: pd.DataFrame,
    corr_notes: List[str],
    etf_coverage: pd.DataFrame,
    data_notes: List[str],
    principal: float,
    turnover_notes: List[str],
    sample_insufficient: bool,
    tej_sha: List[str],
) -> None:
    ensure_out(out_dir)
    lines: List[str] = []
    lines.append("# 候選策略研究報告（LV 低波動、XA 跨資產動能）\n")
    if sample_insufficient:
        lines.append("**樣本不足**\n")
    lines.append(f"產生時間：{datetime.now().strftime('%Y-%m-%d %H:%M')} 台北\n")

    lines.append("## 假設與資料來源\n")
    for a in assumptions:
        lines.append(f"- {a}")
    for n in data_notes:
        lines.append(f"- {n}")
    for ts in tej_sha:
        lines.append(f"- {ts}")
    lines.append(f"- 假設本金：{principal:,.0f} 新台幣。")
    lines.append("- 稅率一律 0.3%（比實際規定保守：債券 ETF 目前免稅，00635U、0050 是 0.1%）。")
    lines.append("- 產業別使用目前分類，有輕微前視偏誤。")
    lines.append("- 最大回撤統一係數使用全期資料，有前視偏誤。係數 > 1 時融資成本未計算。")
    lines.append("")

    lines.append("## 評估期間\n")
    lv_s, lv_e, lv_n = lv_period
    xa_s, xa_e, xa_n = xa_period
    lines.append(f"- LV 段：{lv_s} ～ {lv_e}，{lv_n} 個月（對比 v5 {v5_n} 個月，少 {v5_n - lv_n} 個月）。")
    lines.append(f"- XA 段：{xa_s} ～ {xa_e}，{xa_n} 個月（對比 v5 {v5_n} 個月，少 {v5_n - xa_n} 個月）。")
    lines.append("")

    lines.append("## 單獨績效\n")
    lines.append("Sharpe = 月報酬平均 ÷ 標準差 × √12（無風險利率 0）。")
    lines.append("| 策略 | 期間 | 成本 | 年化% | 波動% | Sharpe | 月頻MDD% | 日頻MDD% |")
    lines.append("|------|------|------|-------|-------|--------|----------|----------|")
    for label, m in metrics.items():
        if not m:
            continue
        dmd = m.get("daily_mdd")
        dmd_s = f"{dmd:.2f}" if isinstance(dmd, (int, float)) and not np.isnan(dmd) else ""
        cost = "含" if m.get("with_cost") else "不含"
        lines.append(
            f"| {label} | {m.get('period','')} | {cost} | "
            f"{m.get('cagr_pct', np.nan):.2f} | {m.get('ann_vol_pct', np.nan):.2f} | "
            f"{m.get('sharpe', np.nan):.3f} | {m.get('mdd_pct', np.nan):.2f} | {dmd_s} |"
        )
    lines.append("")
    for tn in turnover_notes:
        lines.append(f"- {tn}")
    lines.append("")

    lines.append("## 最大回撤統一後比較\n")
    lines.append("用 scale_returns 讓該段最大回撤等於同期 NN3。用了全期資料，有前視偏誤。")
    for name, k in scale_factors.items():
        note = "（係數 > 1，融資成本未計算）" if k > 1 else ""
        lines.append(f"- {name}: {k:.4f}{note}")
    lines.append("")
    if scaled_comparison is not None and not scaled_comparison.empty:
        lines.append(_md_table(scaled_comparison, "項目"))
        lines.append("")

    lines.append("## 相關係數\n")
    lines.append("NN3 沒有日報酬，所以和 NN3 只算月報酬。")
    for note in corr_notes:
        lines.append(f"- {note}")
    lines.append("")

    lines.append("## 加入現有組合\n")
    lines.append("基準 = 0.6 × NN3 + 0.4 × A1（0.3% 稅），每月再平衡。")
    lines.append("主表（不縮放）：")
    lines.append(_md_table(combo_add, "組合"))
    lines.append("\n附表（先依 AC-10 縮放）：")
    lines.append(_md_table(combo_add_scaled, "組合"))
    lines.append("")

    lines.append("## ETF 覆蓋\n")
    if etf_coverage is not None and not etf_coverage.empty:
        lines.append(_md_table(etf_coverage, ""))
    lines.append("")

    lines.append("## 安全與非目標\n")
    lines.append("- 不連任何券商、不下任何單、不讀寫交易紀錄或帳戶檔。")
    lines.append("- 不修改每日系統或排程。")
    lines.append("- 不做參數最佳化。\n")

    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
