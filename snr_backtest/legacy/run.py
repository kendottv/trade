#!/workspace/trade/.venv/bin/python
"""Download cache + backtest both SNR-gated strategies (and raw baselines).

Usage:
    /workspace/trade/.venv/bin/python /workspace/trade/run.py
    /workspace/trade/.venv/bin/python /workspace/trade/run.py --download
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as _fm

_CJK_FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
if Path(_CJK_FONT).exists():
    try:
        _fm.fontManager.addfont(_CJK_FONT)
    except Exception:
        pass
    plt.rcParams["font.sans-serif"] = ["Noto Sans CJK TC", "Noto Sans CJK JP", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
import pandas as pd

from config import (
    BREAKOUT_SNR_MIN,
    END_DATE,
    INITIAL_CAPITAL,
    PULLBACK_SNR_MAX,
    REPORTS_DIR,
    SLICE_3Y_START,
    SNR_N,
    START_DATE,
    TICKERS,
)
from data import load_universe
from engine import run_universe
from metrics import (
    combined_equity,
    combined_summary_row,
    equity_frame,
    lottery_excluded_row,
    summarize_results,
)
from strategies import all_strategies, make_breakout_v2

log = logging.getLogger("trade")


def _pct(x) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "n/a"
    return f"{x*100:.1f}%"


def _num(x, nd=2) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    if isinstance(x, float) and math.isinf(x):
        return "inf"
    return f"{x:.{nd}f}"


def write_strategy_reports(spec, results) -> tuple[pd.DataFrame, dict]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    name = spec.name
    trades = pd.concat(
        [r.trades for r in results if r.trades is not None and len(r.trades)],
        ignore_index=True,
    ) if any(r.trades is not None and len(r.trades) for r in results) else pd.DataFrame()
    cols = [
        "date", "ticker", "name", "action", "reason", "price", "shares",
        "cash", "equity", "snr", "commission", "tax",
    ]
    if trades.empty:
        trades = pd.DataFrame(columns=cols)
    else:
        for c in cols:
            if c not in trades.columns:
                trades[c] = ""
        trades = trades[cols]
    trades.to_csv(REPORTS_DIR / f"{name}_trades.csv", index=False, encoding="utf-8-sig")

    summary = summarize_results(results)
    comb = combined_summary_row(results, summary)
    comb_x = lottery_excluded_row(results)
    summary = pd.concat([summary, pd.DataFrame([comb, comb_x])], ignore_index=True)
    summary.to_csv(REPORTS_DIR / f"{name}_summary.csv", index=False, encoding="utf-8-sig")

    eq = equity_frame(results)
    eq.index.name = "date"
    eq.to_csv(REPORTS_DIR / f"{name}_equity.csv", encoding="utf-8-sig", date_format="%Y-%m-%d")

    _plot_equity(eq, spec, REPORTS_DIR / f"{name}_equity.png")
    return summary, comb


def _plot_equity(eq: pd.DataFrame, spec, path: Path) -> None:
    if eq is None or eq.empty:
        return
    fig, ax = plt.subplots(figsize=(11, 6))
    tickers = [c for c in eq.columns if c != "total"]
    for col in tickers:
        label = f"{TICKERS.get(col, col)} {col}"
        ax.plot(eq.index, eq[col] / 1e6, lw=1.0, alpha=0.85, label=label)
    if "total" in eq.columns:
        ax.plot(
            eq.index, eq["total"] / len(tickers) / 1e6,
            color="black", lw=2.0, ls="--", label="等權平均",
        )
    ax.set_title(f"{spec.name} 權益曲線（百萬 TWD / 單股 1M 帳戶）")
    ax.set_ylabel("權益（百萬 TWD）")
    ax.legend(fontsize=8, ncol=2, loc="upper left")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _md_table(df: pd.DataFrame, cols: list[str]) -> str:
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    lines = [header, sep]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r.get(c, "")
            if c in ("win_rate", "avg_win", "avg_loss", "total_return", "max_drawdown", "max_dd",
                     "cagr", "expectancy", "exposure", "total_return_no_5314",
                     "win_rate_no_5314", "expectancy_no_5314", "max_dd_no_5314"):
                cells.append(_pct(v) if pd.notna(v) else "n/a")
            elif c in ("profit_factor", "avg_snr_win", "avg_snr_loss"):
                cells.append(_num(v, 2))
            elif c in ("final_equity",):
                cells.append(f"{v:,.0f}" if pd.notna(v) else "n/a")
            else:
                cells.append(str(v) if v == v else "")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def build_comparison(all_summ: dict[str, pd.DataFrame], slice_summ: dict[str, pd.DataFrame], failed: list[str]) -> str:
    """Traditional Chinese comparison, honest about SNR, 世紀, and the bull market."""
    def ew(name: str, store: dict) -> pd.Series:
        df = store[name]
        row = df[df["ticker"] == "EQUAL_WEIGHT"]
        if row.empty:
            return df.iloc[-1]
        return row.iloc[0]

    def names_help_hurt(df: pd.DataFrame) -> tuple[str, str]:
        sub = df[~df["ticker"].isin(("EQUAL_WEIGHT", "EQUAL_WEIGHT_NO_5314"))].copy()
        if sub.empty:
            return "無", "無"
        sub = sub.sort_values("total_return", ascending=False)
        top = sub.head(3)
        bot = sub.tail(3).iloc[::-1]
        def fmt(r):
            return f"{r['name']}（{r['ticker']}，{_pct(r['total_return'])}）"
        return "、".join(fmt(r) for _, r in top.iterrows()), "、".join(fmt(r) for _, r in bot.iterrows()) + "（相對最弱，報酬仍可能為正）"

    b1, p1 = ew("breakout_v1", all_summ), ew("pullback_v1", all_summ)
    br, pr = ew("breakout_raw", all_summ), ew("pullback_raw", all_summ)

    help_b, hurt_b = names_help_hurt(all_summ["breakout_v1"])
    help_p, hurt_p = names_help_hurt(all_summ["pullback_v1"])

    def snr_note(df: pd.DataFrame) -> str:
        sub = df[~df["ticker"].isin(("EQUAL_WEIGHT", "EQUAL_WEIGHT_NO_5314"))]
        w = sub["avg_snr_win"].mean(skipna=True)
        l = sub["avg_snr_loss"].mean(skipna=True)
        return f"贏邊平均 SNR={_num(w, 3)}，輸邊平均 SNR={_num(l, 3)}"

    # Did SNR help? Compare equal-weight total return and win rate.
    def helped(gated, raw, higher_is_better_keys=("total_return", "win_rate", "expectancy")):
        notes = []
        for k in higher_is_better_keys:
            g, r = gated[k], raw[k]
            if pd.isna(g) or pd.isna(r):
                continue
            diff = g - r
            notes.append(f"{k}: 有閘 {_pct(g) if k != 'profit_factor' else _num(g)} vs 無閘 {_pct(r) if k != 'profit_factor' else _num(r)}（差 {diff:+.1%}）")
        ret_better = gated["total_return"] > raw["total_return"]
        wr_better = gated["win_rate"] > raw["win_rate"]
        return ret_better, wr_better, notes

    b_ret, b_wr, b_notes = helped(b1, br)
    p_ret, p_wr, p_notes = helped(p1, pr)

    snr_helped_breakout = b_ret or b_wr
    snr_helped_pullback = p_ret or p_wr

    lines = []
    lines.append("# 台股量化回測比較報告")
    lines.append("")
    lines.append(f"- 主樣本：**{START_DATE} → {END_DATE}**（約五年，結束日為資料最後一筆、不晚於 2026-08-13）")
    lines.append(f"- 三年切片：**{SLICE_3Y_START} → {END_DATE}**（獨立重跑，非把五年倉位硬切）")
    lines.append("- 執行假設：訊號在 t 收盤產生，**下一根開盤成交**；台股成本（佣金 0.1425%、最低 20 元、賣出證交稅 0.3%）；**1 張 = 1000 股**，不允許碎股；單檔獨立 100 萬紙上帳戶。")
    lines.append("- **SNR 是訊噪比（Kaufman efficiency ratio），高 = 乾淨趨勢。** 預設 n=20；突破單要求 SNR≥0.40，拉回單要求 SNR≤0.25。")
    lines.append("- v1 **沒有使用 TWII 保險**（舊版路徑依賴、容易前瞻），請勿與舊 CSV 的保險損益直接對齊。")
    lines.append("")
    lines.append("## 策略規則（簡述）")
    lines.append("")
    lines.append(f"- **breakout_v1**：收盤突破「前 20 日最高價」（不含當日），且 SNR_{SNR_N} ≥ {BREAKOUT_SNR_MIN:.2f}。停利 +25%、停損 -20%（同根 K 兩觸則視為先停損）。連續 3 日收盤跌破前 20 日最低 → 次日開盤出清。")
    lines.append(f"- **pullback_v1**：收盤在 60 日均線之上，且收盤落在 20 日均線的 {0.97:.2f}–{1.01:.2f} 倍（拉回到均線附近），且 SNR_{SNR_N} ≤ {PULLBACK_SNR_MAX:.2f}。停利 +8%、停損 -4%（同根先停損）。")
    lines.append("- **breakout_raw / pullback_raw**：同一套進出場，但**關掉 SNR 閘門**，用來回答「SNR 有沒有幫忙」。")
    lines.append("")
    lines.append("## 五年樣本：等權合計（10 檔 × 100 萬）")
    lines.append("")

    ew_tbl = pd.DataFrame([
        {**{"strategy": k}, **ew(k, all_summ).to_dict()}
        for k in ("breakout_v1", "breakout_raw", "pullback_v1", "pullback_raw")
    ])
    lines.append(_md_table(
        ew_tbl,
        ["strategy", "trades", "win_rate", "avg_win", "avg_loss", "profit_factor",
         "expectancy", "total_return", "max_drawdown", "cagr", "final_equity",
         "avg_snr_win", "avg_snr_loss"],
    ))
    lines.append("")
    lines.append("### 勝率與期望值（成本後）")
    lines.append("")
    lines.append(
        f"- 突破 **breakout_v1** 勝率 {_pct(b1['win_rate'])}，成本後期望值 {_pct(b1['expectancy'])}／筆，"
        f"等權總報酬 {_pct(b1['total_return'])}，CAGR {_pct(b1['cagr'])}，最大回撤 {_pct(b1['max_drawdown'])}。"
    )
    lines.append(
        f"- 拉回 **pullback_v1** 勝率 {_pct(p1['win_rate'])}，成本後期望值 {_pct(p1['expectancy'])}／筆，"
        f"等權總報酬 {_pct(p1['total_return'])}，CAGR {_pct(p1['cagr'])}，最大回撤 {_pct(p1['max_drawdown'])}。"
    )
    if p1["win_rate"] > b1["win_rate"]:
        lines.append("- 拉回策略的**勝率確實較高**（符合「小賺小停、高勝率」設計），但這不自動等於更高總報酬：盈虧比被壓在約 +8% / -4%，再加上來回成本（約 0.6%），期望值可能仍薄。")
    else:
        lines.append("- 拉回策略**並未**打出比較高的勝率。在 2021–2026 半導體大多頭裡，價格常不在 20 日均線附近停留，或 SNR 偏低的盤整段本身就少；高勝率假設在這段樣本不成立。")
    if b1["expectancy"] > 0:
        lines.append("- 突破策略在成本後期望值為正。")
    else:
        lines.append("- 突破策略在成本後期望值**不是正的**——扣掉佣金與證交稅後，紙上「看起來會賺」的突破不一定活得下來。")
    if p1["expectancy"] > 0:
        lines.append("- 拉回策略在成本後期望值為正。")
    else:
        lines.append("- 拉回策略在成本後期望值**不是正的**。緊停損在台股電子股的缺口裡很容易被掃，這是設計代價，不是實作 bug。")
    lines.append("")
    lines.append("### SNR 閘門有沒有幫忙？")
    lines.append("")
    lines.append(f"- 突破（有閘 vs 無閘）：總報酬 {'有改善' if b_ret else '沒有改善'}，勝率 {'有改善' if b_wr else '沒有改善'}。")
    for n in b_notes:
        lines.append(f"  - {n}")
    lines.append(f"- 拉回（有閘 vs 無閘）：總報酬 {'有改善' if p_ret else '沒有改善'}，勝率 {'有改善' if p_wr else '沒有改善'}。")
    for n in p_notes:
        lines.append(f"  - {n}")
    if snr_helped_breakout or snr_helped_pullback:
        lines.append("- **結論（五年）**：SNR 閘門**有部分幫助**，但不是萬靈丹；它主要是在過濾「不該做的市場狀態」，成交筆數會變少，統計更吵。")
    else:
        lines.append("- **結論（五年）**：在這段樣本裡，SNR 閘門**沒有清楚幫上忙**（總報酬與勝率都沒有同時變好）。它仍然是合理的狀態過濾，但不應因為「加了訊噪比」就宣稱策略升級。")
    lines.append(f"- breakout_v1 {snr_note(all_summ['breakout_v1'])}。")
    lines.append(f"- pullback_v1 {snr_note(all_summ['pullback_v1'])}。")
    lines.append("- 若贏邊 SNR 並沒有系統性高於輸邊，代表「趨勢很乾淨」與「這筆會賺」在本樣本相關性弱，不要過度解讀單一門檻。")
    lines.append("")
    lines.append("### 個股：誰幫忙、誰拖累")
    lines.append("")
    lines.append(f"- **breakout_v1** 貢獻前三：{help_b}。拖累：{hurt_b}。")
    lines.append(f"- **pullback_v1** 貢獻前三：{help_p}。拖累：{hurt_p}。")
    lines.append("- **世紀（5314.TWO）是樂透型飆股**，單檔報酬可以扭曲整份表。若拿掉世紀後結論翻盤，就不要把策略說成「對電子股有效」，那只是對這一檔有效。")
    lines.append("")

    # per-ticker dump for mains
    lines.append("#### breakout_v1 分檔")
    lines.append("")
    lines.append(_md_table(
        all_summ["breakout_v1"],
        ["ticker", "name", "trades", "win_rate", "profit_factor", "total_return", "max_drawdown", "cagr", "avg_snr_win", "avg_snr_loss"],
    ))
    lines.append("")
    lines.append("#### pullback_v1 分檔")
    lines.append("")
    lines.append(_md_table(
        all_summ["pullback_v1"],
        ["ticker", "name", "trades", "win_rate", "profit_factor", "total_return", "max_drawdown", "cagr", "avg_snr_win", "avg_snr_loss"],
    ))
    lines.append("")

    if slice_summ:
        lines.append(f"## 三年切片（{SLICE_3Y_START} → {END_DATE}）")
        lines.append("")
        s_tbl = pd.DataFrame([
            {**{"strategy": k}, **ew(k, slice_summ).to_dict()}
            for k in ("breakout_v1", "breakout_raw", "pullback_v1", "pullback_raw")
            if k in slice_summ
        ])
        if not s_tbl.empty:
            lines.append(_md_table(
                s_tbl,
                ["strategy", "trades", "win_rate", "expectancy", "total_return", "max_drawdown", "cagr"],
            ))
            sb, sp = ew("breakout_v1", slice_summ), ew("pullback_v1", slice_summ)
            sbr, spr = ew("breakout_raw", slice_summ), ew("pullback_raw", slice_summ)
            lines.append("")
            lines.append(
                f"- 三年切片裡，breakout_v1 勝率 {_pct(sb['win_rate'])}、總報酬 {_pct(sb['total_return'])}；"
                f"pullback_v1 勝率 {_pct(sp['win_rate'])}、總報酬 {_pct(sp['total_return'])}。"
            )
            lines.append(
                f"- 相對 raw：突破總報酬差 {(sb['total_return']-sbr['total_return']):+.1%}，"
                f"拉回總報酬差 {(sp['total_return']-spr['total_return']):+.1%}。"
            )
            lines.append("- 三年切片更重疊 2023–2026 電子大多頭，**更不能**外推到空頭或高利率年份。")
        lines.append("")

    lines.append("## 誠實的限制")
    lines.append("")
    lines.append("- **2021–2026 台股半導體／AI 鏈是極端大多頭。** 突破類策略在這段會被行情抬轎；換成 2018 或 2022 那種環境，同一套規則很可能是另一份成績單。本報告**沒有**做空頭樣本外測試。")
    lines.append("- 單檔 100 萬、全倉 1 張整數，與「十檔平分一個 100 萬」不同。不要拿本報告的等權合計去對舊版 all-in 單一 CSV。")
    lines.append("- 未模擬漲跌停無法成交、未模擬盤中流動性、未加滑價。下一根開盤成交在跳空時會比「用收盤價成交」更痛，這是刻意偏保守。")
    lines.append("- 價格走 yfinance `auto_adjust=True`，權息調整後的價格與真實撮合價不會完全一致，張數計算是近似。")
    lines.append("- 沒有走 TWII 保險；舊 `trade.py` / `trade2.py` 若因為大盤濾網少做了某些單，本回測不會複製那些漏網／誤殺。")
    if failed:
        lines.append(f"- **下載失敗、已跳過**：{', '.join(failed)}")
    else:
        lines.append("- 十檔與 ^TWII 皆成功下載（或命中快取）。")
    lines.append("")
    lines.append("—— 報告由 `run.py` 依本次回測數字自動產生，不要手工改結論。")
    lines.append("")
    return "\n".join(lines)


def print_console(all_summ: dict[str, pd.DataFrame]) -> None:
    print("\n======== 回測摘要（等權合計，成本後） ========")
    hdr = f"{'strategy':16} {'trades':>6} {'win':>8} {'exp':>8} {'ret':>9} {'maxDD':>8} {'CAGR':>8} {'PF':>6}"
    print(hdr)
    print("-" * len(hdr))
    keys = [k for k in ("breakout_v1", "breakout_v2", "breakout_raw", "pullback_v1", "pullback_raw") if k in all_summ]
    for k in keys:
        df = all_summ[k]
        row = df[df["ticker"] == "EQUAL_WEIGHT"].iloc[0]
        pf = row["profit_factor"]
        pf_s = "inf" if (isinstance(pf, float) and math.isinf(pf)) else f"{pf:.2f}"
        print(
            f"{k:16} {int(row['trades']):6d} {_pct(row['win_rate']):>8} "
            f"{_pct(row['expectancy']):>8} {_pct(row['total_return']):>9} "
            f"{_pct(row['max_drawdown']):>8} {_pct(row['cagr']):>8} {pf_s:>6}"
        )
    print("\n—— 分檔 win_rate / total_return（breakout_v1 | pullback_v1）")
    b = all_summ["breakout_v1"].set_index("ticker")
    p = all_summ["pullback_v1"].set_index("ticker")
    for t, name in TICKERS.items():
        if t not in b.index:
            continue
        rb, rp = b.loc[t], p.loc[t]
        print(
            f"  {t:10} {name:6}  "
            f"BO {int(rb['trades']):3d} {_pct(rb['win_rate']):>7} {_pct(rb['total_return']):>8}  |  "
            f"PB {int(rp['trades']):3d} {_pct(rp['win_rate']):>7} {_pct(rp['total_return']):>8}"
        )
    print("==============================================\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Taiwan stock backtester")
    parser.add_argument("--download", action="store_true", help="force re-download (ignore cache)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    log.info("loading universe  warmup→end, force=%s", args.download)
    prices, failed = load_universe(force_download=args.download)
    for t in failed:
        log.warning("FAILED ticker: %s", t)
    ok = [t for t in TICKERS if t in prices]
    log.info("prices ready: %d/%d names", len(ok), len(TICKERS))
    if not ok:
        log.error("no price data — abort")
        return 1

    specs = all_strategies()
    all_summ: dict[str, pd.DataFrame] = {}
    for spec in specs:
        log.info("backtest %s  %s → %s", spec.name, START_DATE, END_DATE)
        results = run_universe(prices, spec, INITIAL_CAPITAL, START_DATE, END_DATE)
        summary, _ = write_strategy_reports(spec, results)
        all_summ[spec.name] = summary
        n_tr = int(summary.loc[~summary["ticker"].isin(("EQUAL_WEIGHT", "EQUAL_WEIGHT_NO_5314")), "trades"].sum())
        log.info("%s closed round-trips (sum of names) = %d", spec.name, n_tr)

    v2 = make_breakout_v2()
    log.info("backtest %s  %s → %s", v2.name, START_DATE, END_DATE)
    results = run_universe(prices, v2, INITIAL_CAPITAL, START_DATE, END_DATE)
    summary, _ = write_strategy_reports(v2, results)
    all_summ[v2.name] = summary
    n_tr = int(summary.loc[~summary["ticker"].isin(("EQUAL_WEIGHT", "EQUAL_WEIGHT_NO_5314")), "trades"].sum())
    log.info("%s closed round-trips (sum of names) = %d", v2.name, n_tr)

    slice_summ: dict[str, pd.DataFrame] = {}
    for spec in specs:
        log.info("3y slice %s  %s → %s", spec.name, SLICE_3Y_START, END_DATE)
        results = run_universe(prices, spec, INITIAL_CAPITAL, SLICE_3Y_START, END_DATE)
        s = summarize_results(results)
        comb = combined_summary_row(results, s)
        s = pd.concat([s, pd.DataFrame([comb])], ignore_index=True)
        slice_summ[spec.name] = s
    slice_rows = []
    for k, df in slice_summ.items():
        tmp = df.copy()
        tmp.insert(0, "strategy", k)
        slice_rows.append(tmp)
    pd.concat(slice_rows, ignore_index=True).to_csv(
        REPORTS_DIR / "slice_3y_summary.csv", index=False, encoding="utf-8-sig"
    )

    md = build_comparison(all_summ, slice_summ, failed)
    (REPORTS_DIR / "comparison.md").write_text(md, encoding="utf-8")

    print_console(all_summ)
    log.info("reports written under %s", REPORTS_DIR)
    if failed:
        log.warning("download failures: %s", ", ".join(failed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
