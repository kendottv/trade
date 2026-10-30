#!/workspace/trade/.venv/bin/python
"""OOS-first grid for breakout_v2. Decision metric is out-of-sample, not IS.

Reduced grid (24):
    snr_min {0.30, 0.40, 0.50}
    vol_mult {0, 1.2}
    twii_filter {False, True}
    no_chase {False, True}
    snr_rising=False, trail=False

Then snr_rising / trail extras on the top 5 OOS configs.

Usage:
    /workspace/trade/.venv/bin/python /workspace/trade/tune.py
"""

from __future__ import annotations

import itertools
import json
import logging
import math
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from config import (
    END_DATE,
    INITIAL_CAPITAL,
    IS_END,
    IS_START,
    LOTTERY_TICKER,
    OOS_END,
    OOS_START,
    REPORTS_DIR,
    START_DATE,
    TICKERS,
)
from data import load_universe
from engine import run_universe
from metrics import combined_summary_row, lottery_excluded_row, summarize_results
from run import write_strategy_reports, _md_table, _pct, _num
from strategies import StrategySpec, make_breakout_v2

log = logging.getLogger("tune")

SNR_MINS = (0.30, 0.40, 0.50)
VOL_MULTS = (0.0, 1.2)
TWII_FLAGS = (False, True)
NO_CHASE_FLAGS = (False, True)

MIN_TRADES = 20
MIN_WIN_RATE = 0.55
MIN_PF = 1.2


def combo_id(snr_min, vol_mult, twii_filter, no_chase, snr_rising=False, trail=False) -> str:
    return (
        f"snr{snr_min:.2f}_vol{vol_mult:g}"
        f"_twii{int(twii_filter)}_chase{int(no_chase)}"
        f"_rise{int(snr_rising)}_trail{int(trail)}"
    )


def spec_from_params(p: dict, name: str = "breakout_v2") -> StrategySpec:
    return make_breakout_v2(
        snr_min=float(p["snr_min"]),
        snr_rising=bool(p["snr_rising"]),
        vol_mult=float(p["vol_mult"]),
        twii_filter=bool(p["twii_filter"]),
        no_chase=bool(p["no_chase"]),
        trail=bool(p["trail"]),
        name=name,
    )


def _finite(x, default=0.0) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    if math.isnan(v) or math.isinf(v):
        return default
    return v


def metrics_from_results(results, params: dict, stage: str, window: str) -> dict:
    ew = combined_summary_row(results, pd.DataFrame())
    nx = lottery_excluded_row(results, LOTTERY_TICKER)
    pf = ew["profit_factor"]
    pf_x = nx["profit_factor"]
    row = {
        "combo_id": combo_id(
            params["snr_min"], params["vol_mult"], params["twii_filter"],
            params["no_chase"], params["snr_rising"], params["trail"],
        ),
        "stage": stage,
        "window": window,
        "snr_min": params["snr_min"],
        "snr_rising": int(bool(params["snr_rising"])),
        "vol_mult": params["vol_mult"],
        "twii_filter": int(bool(params["twii_filter"])),
        "no_chase": int(bool(params["no_chase"])),
        "trail": int(bool(params["trail"])),
        "trades": int(ew["trades"]),
        "n_trades": int(ew["trades"]),
        "win_rate": ew["win_rate"],
        "expectancy": ew["expectancy"],
        "profit_factor": pf if not (isinstance(pf, float) and math.isinf(pf)) else 99.0,
        "total_return": ew["total_return"],
        "max_dd": ew["max_drawdown"],
        "cagr": ew["cagr"],
        "n_wins": int(ew["n_wins"]),
        "n_losses": int(ew["n_losses"]),
        "trades_no_5314": int(nx["trades"]),
        "win_rate_no_5314": nx["win_rate"],
        "expectancy_no_5314": nx["expectancy"],
        "profit_factor_no_5314": pf_x if not (isinstance(pf_x, float) and math.isinf(pf_x)) else 99.0,
        "total_return_no_5314": nx["total_return"],
        "max_dd_no_5314": nx["max_drawdown"],
        "cagr_no_5314": nx["cagr"],
    }
    return row


def run_combo(prices, params: dict, start: str, end: str, stage: str, window: str):
    spec = spec_from_params(params, name=combo_id(
        params["snr_min"], params["vol_mult"], params["twii_filter"],
        params["no_chase"], params["snr_rising"], params["trail"],
    ))
    results = run_universe(prices, spec, INITIAL_CAPITAL, start, end)
    return metrics_from_results(results, params, stage, window), results


def reduced_grid() -> list[dict]:
    out = []
    for snr_min, vol_mult, twii, chase in itertools.product(
        SNR_MINS, VOL_MULTS, TWII_FLAGS, NO_CHASE_FLAGS
    ):
        out.append({
            "snr_min": snr_min,
            "snr_rising": False,
            "vol_mult": vol_mult,
            "twii_filter": twii,
            "no_chase": chase,
            "trail": False,
        })
    return out


def extra_variants(base: dict) -> list[dict]:
    """snr_rising / trail on a reduced-grid winner (skip the already-run 0/0)."""
    variants = []
    for rise, trail in ((True, False), (False, True), (True, True)):
        p = dict(base)
        p["snr_rising"] = rise
        p["trail"] = trail
        variants.append(p)
    return variants


def passes_constraints(row: dict) -> bool:
    pf = _finite(row["profit_factor"])
    return (
        int(row["trades"]) >= MIN_TRADES
        and _finite(row["win_rate"]) >= MIN_WIN_RATE
        and pf >= MIN_PF
    )


def select_winner(oos_rows: list[dict]) -> tuple[dict, str]:
    """Return (winning oos row, reason)."""
    enough = [r for r in oos_rows if int(r["trades"]) >= MIN_TRADES]
    passed = [r for r in enough if passes_constraints(r)]
    if passed:
        passed.sort(
            key=lambda r: (-_finite(r["expectancy"]), abs(_finite(r["max_dd"])))
        )
        return passed[0], (
            f"OOS constraints met (trades>={MIN_TRADES}, WR>={MIN_WIN_RATE:.0%}, "
            f"PF>={MIN_PF}); highest OOS expectancy, tie-break lower |max_dd|"
        )
    if enough:
        enough.sort(
            key=lambda r: (-_finite(r["expectancy"]), abs(_finite(r["max_dd"])))
        )
        return enough[0], (
            "CONSTRAINTS NOT MET — no combo had OOS WR>=55% and PF>=1.2 with "
            f">={MIN_TRADES} trades; fell back to highest OOS expectancy among "
            f">={MIN_TRADES}-trade combos"
        )
    oos_rows = sorted(
        oos_rows, key=lambda r: (-_finite(r["expectancy"]), abs(_finite(r["max_dd"])))
    )
    return oos_rows[0], "CONSTRAINTS NOT MET — fewer than 20 OOS trades on every combo; highest expectancy anyway"


def params_of(row: dict) -> dict:
    return {
        "snr_min": float(row["snr_min"]),
        "snr_rising": bool(int(row["snr_rising"])),
        "vol_mult": float(row["vol_mult"]),
        "twii_filter": bool(int(row["twii_filter"])),
        "no_chase": bool(int(row["no_chase"])),
        "trail": bool(int(row["trail"])),
    }


def patch_config(params: dict) -> None:
    """Rewrite BREAKOUT_V2_* defaults in config.py to the OOS winner."""
    path = ROOT / "config.py"
    text = path.read_text(encoding="utf-8")

    def sub_bool(key: str, val: bool) -> None:
        nonlocal text
        text = re.sub(
            rf"^({key}\s*=\s*)(True|False)",
            rf"\g<1>{'True' if val else 'False'}",
            text,
            count=1,
            flags=re.M,
        )

    def sub_float(key: str, val: float) -> None:
        nonlocal text
        text = re.sub(
            rf"^({key}\s*=\s*)[-+0-9.eE]+",
            rf"\g<1>{val}",
            text,
            count=1,
            flags=re.M,
        )

    sub_float("BREAKOUT_V2_SNR_MIN", float(params["snr_min"]))
    sub_bool("BREAKOUT_V2_SNR_RISING", bool(params["snr_rising"]))
    sub_float("BREAKOUT_V2_VOL_MULT", float(params["vol_mult"]))
    sub_bool("BREAKOUT_V2_TWII_FILTER", bool(params["twii_filter"]))
    sub_bool("BREAKOUT_V2_NO_CHASE", bool(params["no_chase"]))
    sub_bool("BREAKOUT_V2_TRAIL", bool(params["trail"]))
    path.write_text(text, encoding="utf-8")
    log.info("config.py BREAKOUT_V2_* updated to %s", params)


def _row_by_id(rows: list[dict], cid: str) -> dict | None:
    for r in rows:
        if r["combo_id"] == cid:
            return r
    return None


def build_v2_md(
    winner: dict,
    reason: str,
    constraints_met: bool,
    is_rows: list[dict],
    oos_rows: list[dict],
    v1_is: dict,
    v1_oos: dict,
    v1_full: dict,
    v1_full_x: dict,
    v2_is: dict,
    v2_oos: dict,
    v2_full: dict,
    v2_full_x: dict,
    v2_full_summary: pd.DataFrame,
    v1_full_summary: pd.DataFrame,
) -> str:
    p = params_of(winner)
    cid = winner["combo_id"]
    is_w = _row_by_id(is_rows, cid) or {}
    oos_w = winner

    def fmt_row(r, keys=("trades", "win_rate", "expectancy", "profit_factor", "total_return", "max_dd")):
        if not r:
            return "n/a"
        bits = []
        for k in keys:
            v = r.get(k, r.get("max_drawdown") if k == "max_dd" else None)
            if k in ("win_rate", "expectancy", "total_return", "max_dd", "max_drawdown", "cagr"):
                bits.append(f"{k}={_pct(v)}")
            elif k == "profit_factor":
                bits.append(f"PF={_num(v, 2)}")
            else:
                bits.append(f"{k}={v}")
        return "，".join(bits)

    lines = []
    lines.append("# breakout_v2 比較報告（OOS 選參）")
    lines.append("")
    lines.append("決策指標是**樣本外（OOS）**，不是樣本內報酬。沒有把拉回策略當主路徑再優化。")
    lines.append("")
    lines.append("## 相對 v1 改了什麼")
    lines.append("")
    lines.append("- **核心不變**：收盤突破前 20 日最高（不含當日）、SNR_20 閘門、停利 +25%／停損 -20%（同根先停損）、連續 3 日收盤跌破前 20 日最低 → 次日開盤出清。成本、1 張、下一根開盤成交都沒改。")
    lines.append("- **v2 可選濾網**（由 OOS 網格決定開不開）：")
    lines.append("  1. `snr_min`：Kaufman SNR_20 門檻（網格 0.30 / 0.40 / 0.50）")
    lines.append("  2. `snr_rising`：SNR_20 > SMA(SNR_20, 5)（趨勢品質在改善）")
    lines.append("  3. `vol_mult`：成交量 ≥ vol_mult × 20 日均量（0 = 關；網格另測 1.2）")
    lines.append("  4. `twii_filter`：僅在 ^TWII 收盤 > SMA 60 時進場")
    lines.append("  5. `no_chase`：收盤 > 前 20 日高 × 1.08 視為追價過遠，跳過")
    lines.append("  6. `trail`：未實現（當根最高價相對進場）≥ 12% 後，若收盤跌破前 15 日最低 → 次日開盤出（硬停利停損仍在）")
    lines.append("- 網格是**縮小版** 3×2×2×2 = 24 組（snr_rising / trail 預設關），再只對 OOS 前 5 名加測 rising / trail。不是 160 組全搜，故意避免在 2021–2026 半導體大多頭上曲線擬合。")
    lines.append("")
    lines.append("## 網格贏家與為什麼（看 OOS）")
    lines.append("")
    lines.append(f"- **選中 combo**：`{cid}`")
    lines.append(
        f"- 參數：snr_min={p['snr_min']:.2f}，snr_rising={p['snr_rising']}，"
        f"vol_mult={p['vol_mult']:g}，twii_filter={p['twii_filter']}，"
        f"no_chase={p['no_chase']}，trail={p['trail']}"
    )
    lines.append(f"- **選參規則**：{reason}")
    if not constraints_met:
        lines.append("- **警告：OOS 硬條件（≥20 筆、勝率≥55%、PF≥1.2）沒有全部達標。** 下面的 v2 仍是規則下的次佳解，不是「通過健檢」。")
    lines.append("")
    lines.append("| 視窗 | 策略 | trades | win_rate | expectancy | PF | total_return | max_dd | 不含世紀報酬 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")

    def md_line(window, name, r, rx=None):
        if not r:
            return
        pf = r.get("profit_factor")
        tr_x = (rx or r).get("total_return_no_5314", (rx or {}).get("total_return"))
        lines.append(
            f"| {window} | {name} | {int(r.get('trades', r.get('n_trades', 0)))} | "
            f"{_pct(r.get('win_rate'))} | {_pct(r.get('expectancy'))} | {_num(pf, 2)} | "
            f"{_pct(r.get('total_return'))} | {_pct(r.get('max_dd', r.get('max_drawdown')))} | "
            f"{_pct(tr_x) if tr_x is not None else 'n/a'} |"
        )

    md_line("IS 2021-08-13→2024-08-12", "breakout_v1", v1_is)
    md_line("IS 2021-08-13→2024-08-12", "breakout_v2 贏家", is_w if is_w else v2_is)
    md_line("OOS 2024-08-13→2026-08-13", "breakout_v1", v1_oos)
    md_line("OOS 2024-08-13→2026-08-13", "breakout_v2 贏家", oos_w)
    md_line("FULL 2021-08-13→2026-08-13", "breakout_v1", v1_full, v1_full_x)
    md_line("FULL 2021-08-13→2026-08-13", "breakout_v2 贏家", v2_full, v2_full_x)
    lines.append("")
    lines.append(
        f"- 贏家 **OOS**：{fmt_row(oos_w)}；不含世紀：勝率 {_pct(oos_w.get('win_rate_no_5314'))}、"
        f"期望值 {_pct(oos_w.get('expectancy_no_5314'))}、報酬 {_pct(oos_w.get('total_return_no_5314'))}、"
        f"回撤 {_pct(oos_w.get('max_dd_no_5314'))}（{int(oos_w.get('trades_no_5314', 0))} 筆）。"
    )
    if is_w:
        lines.append(
            f"- 同一組 **IS**（只記錄、不拿來選參）：{fmt_row(is_w)}。"
        )
    lines.append(
        f"- v1 同窗 OOS：{fmt_row(v1_oos)}。v2 若只在 IS 比較好看、OOS 沒比較穩，就當擬合，不要上槓桿。"
    )
    lines.append("")

    # top OOS table
    top = sorted(oos_rows, key=lambda r: -_finite(r["expectancy"]))[:10]
    lines.append("### OOS 期望值前 10（等權 10 檔）")
    lines.append("")
    top_df = pd.DataFrame(top)
    show = top_df[[
        "combo_id", "stage", "trades", "win_rate", "expectancy", "profit_factor",
        "total_return", "max_dd", "total_return_no_5314",
    ]].copy()
    lines.append(_md_table(
        show,
        ["combo_id", "stage", "trades", "win_rate", "expectancy", "profit_factor",
         "total_return", "max_dd", "total_return_no_5314"],
    ))
    lines.append("")

    lines.append("## 全樣本 v2 vs v1")
    lines.append("")
    lines.append(
        f"- **breakout_v1** 全樣本等權：勝率 {_pct(v1_full.get('win_rate'))}，"
        f"期望值 {_pct(v1_full.get('expectancy'))}／筆，PF {_num(v1_full.get('profit_factor'), 2)}，"
        f"總報酬 {_pct(v1_full.get('total_return'))}，最大回撤 {_pct(v1_full.get('max_drawdown'))}，"
        f"{int(v1_full.get('trades', 0))} 筆。"
    )
    lines.append(
        f"- **breakout_v2** 全樣本等權：勝率 {_pct(v2_full.get('win_rate'))}，"
        f"期望值 {_pct(v2_full.get('expectancy'))}／筆，PF {_num(v2_full.get('profit_factor'), 2)}，"
        f"總報酬 {_pct(v2_full.get('total_return'))}，最大回撤 {_pct(v2_full.get('max_drawdown'))}，"
        f"{int(v2_full.get('trades', 0))} 筆。"
    )
    # honesty vs IS cherry pick
    v2_oos_exp = _finite(oos_w.get("expectancy"))
    v1_oos_exp = _finite(v1_oos.get("expectancy"))
    if v2_oos_exp > v1_oos_exp:
        lines.append("- 在 **OOS** 上 v2 期望值高於 v1；這是這次允許改規則的理由，不是因為全樣本報酬比較大。")
    else:
        lines.append("- 在 **OOS** 上 v2 期望值**沒有**高於 v1。濾網可能只是少做單、全樣本曲線比較平滑，不代表規則比較強。")
    lines.append("")

    lines.append("#### breakout_v2 全樣本分檔")
    lines.append("")
    lines.append(_md_table(
        v2_full_summary,
        ["ticker", "name", "trades", "win_rate", "profit_factor", "expectancy",
         "total_return", "max_drawdown", "cagr"],
    ))
    lines.append("")
    lines.append("#### breakout_v1 全樣本分檔")
    lines.append("")
    lines.append(_md_table(
        v1_full_summary,
        ["ticker", "name", "trades", "win_rate", "profit_factor", "expectancy",
         "total_return", "max_drawdown", "cagr"],
    ))
    lines.append("")

    lines.append("## 含世紀 vs 不含世紀")
    lines.append("")
    lines.append(
        f"- v2 全樣本 **含世紀**：報酬 {_pct(v2_full.get('total_return'))}，勝率 {_pct(v2_full.get('win_rate'))}，{int(v2_full.get('trades', 0))} 筆。"
    )
    lines.append(
        f"- v2 全樣本 **不含世紀**：報酬 {_pct(v2_full_x.get('total_return'))}，勝率 {_pct(v2_full_x.get('win_rate'))}，"
        f"期望值 {_pct(v2_full_x.get('expectancy'))}，PF {_num(v2_full_x.get('profit_factor'), 2)}，"
        f"回撤 {_pct(v2_full_x.get('max_drawdown'))}，{int(v2_full_x.get('trades', 0))} 筆。"
    )
    lines.append(
        f"- v1 全樣本不含世紀：報酬 {_pct(v1_full_x.get('total_return'))}，勝率 {_pct(v1_full_x.get('win_rate'))}。"
    )
    v2_all = _finite(v2_full.get("total_return"))
    v2_x = _finite(v2_full_x.get("total_return"))
    if v2_all > 0 and (v2_all - v2_x) / max(abs(v2_all), 1e-9) > 0.25:
        lines.append("- **世紀仍在主導等權報酬。** 拿掉它之後數字掉一截，就不要把策略說成「對電子股有效」，那只是對這一檔樂透飆股有效。")
    else:
        lines.append("- 拿掉世紀後結論沒有翻盤到「策略只靠這一檔」的程度，但世紀波動仍大，分檔表請自己看，不要只背等權合計。")
    lines.append("- 世紀（5314.TWO）是樂透型飆股，單檔回撤也可以超過 50%。紙上帳戶全倉 1 張，實盤做不到這種報酬路徑。")
    lines.append("")

    lines.append("## 誠實的限制")
    lines.append("")
    lines.append("- **2021–2026 台股半導體／AI 鏈是極端大多頭。** OOS（2024-08-13 → 2026-08-13）幾乎整段都還在這波行情裡，**不是**空頭或高利率年份的樣本外。通過本報告的 OOS 門檻，只代表「在多頭後半段沒有立刻壞掉」，不能外推到 2018、2022 那種環境。")
    lines.append("- 縮小網格仍有過擬合風險：24 組 + 前 5 名的 extras，等於在同一段行情上試了幾十種濾網。OOS 只有約兩年、成交筆數可能只有幾十，期望值的抽樣誤差很大。")
    lines.append("- 選參規則刻意**不最大化 IS 報酬**。若某組 IS 報酬最高但 OOS 勝率／PF 不合格，它不會被選。這降低（但消除不了）曲線擬合。")
    lines.append("- 未模擬漲跌停無法成交、未模擬盤中流動性、未加滑價。下一根開盤成交在跳空時會比收盤價更痛。")
    lines.append("- 價格走 yfinance `auto_adjust=True`，權息調整後的價格與真實撮合價不會完全一致。")
    lines.append("- **這仍是紙上交易。** 沒有實盤成交、沒有心理、沒有部位上限。不要把回測 CAGR 當作出發點。")
    lines.append("- 拉回策略（pullback_v1）五年勝率約 40.7%，這次**沒有**再拿它當主路徑調參。")
    lines.append("")
    lines.append("## 建議寫進 config.py 的預設")
    lines.append("")
    lines.append("```python")
    lines.append(f"BREAKOUT_V2_SNR_MIN = {p['snr_min']}")
    lines.append(f"BREAKOUT_V2_SNR_RISING = {p['snr_rising']}")
    lines.append(f"BREAKOUT_V2_VOL_MULT = {p['vol_mult']}")
    lines.append(f"BREAKOUT_V2_TWII_FILTER = {p['twii_filter']}")
    lines.append(f"BREAKOUT_V2_NO_CHASE = {p['no_chase']}")
    lines.append(f"BREAKOUT_V2_TRAIL = {p['trail']}")
    lines.append("```")
    lines.append("")
    lines.append("跑網格：`/workspace/trade/.venv/bin/python /workspace/trade/tune.py`")
    lines.append("跑全樣本（含 v1 / v2）：`/workspace/trade/.venv/bin/python /workspace/trade/run.py`")
    lines.append("")
    lines.append("—— 報告由 `tune.py` 依本次網格數字自動產生，不要手工改結論。")
    lines.append("")
    return "\n".join(lines)


def ew_from_results(results) -> dict:
    row = combined_summary_row(results, pd.DataFrame())
    row["max_dd"] = row["max_drawdown"]
    x = lottery_excluded_row(results)
    row["total_return_no_5314"] = x["total_return"]
    row["win_rate_no_5314"] = x["win_rate"]
    row["expectancy_no_5314"] = x["expectancy"]
    row["profit_factor_no_5314"] = x["profit_factor"]
    row["max_dd_no_5314"] = x["max_drawdown"]
    row["trades_no_5314"] = x["trades"]
    return row, x


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    log.info("loading universe from cache")
    prices, failed = load_universe(force_download=False)
    if failed:
        log.warning("missing tickers: %s", ", ".join(failed))
    ok = [t for t in TICKERS if t in prices]
    if len(ok) < 8:
        log.error("too few prices (%d) — abort", len(ok))
        return 1

    grid = reduced_grid()
    is_rows: list[dict] = []
    oos_rows: list[dict] = []
    t0 = time.time()
    log.info("reduced grid: %d combos × 10 names × IS+OOS", len(grid))

    for i, params in enumerate(grid, 1):
        cid = combo_id(
            params["snr_min"], params["vol_mult"], params["twii_filter"],
            params["no_chase"], params["snr_rising"], params["trail"],
        )
        is_m, _ = run_combo(prices, params, IS_START, IS_END, "reduced", "IS")
        oos_m, _ = run_combo(prices, params, OOS_START, OOS_END, "reduced", "OOS")
        is_rows.append(is_m)
        oos_rows.append(oos_m)
        log.info(
            "[%d/%d] %s  IS n=%d WR=%.1f%% exp=%.1f%% | OOS n=%d WR=%.1f%% exp=%.1f%% PF=%.2f",
            i, len(grid), cid,
            is_m["trades"], is_m["win_rate"] * 100, is_m["expectancy"] * 100,
            oos_m["trades"], oos_m["win_rate"] * 100, oos_m["expectancy"] * 100,
            oos_m["profit_factor"],
        )

    # top 5 OOS by expectancy among >= MIN_TRADES (fill with others if needed)
    ranked = sorted(oos_rows, key=lambda r: -_finite(r["expectancy"]))
    with_n = [r for r in ranked if int(r["trades"]) >= MIN_TRADES]
    top5 = (with_n + [r for r in ranked if r not in with_n])[:5]
    log.info("top 5 OOS configs for extras: %s", [r["combo_id"] for r in top5])

    seen = {r["combo_id"] for r in oos_rows}
    extra_params = []
    for r in top5:
        for p in extra_variants(params_of(r)):
            cid = combo_id(
                p["snr_min"], p["vol_mult"], p["twii_filter"],
                p["no_chase"], p["snr_rising"], p["trail"],
            )
            if cid not in seen:
                extra_params.append(p)
                seen.add(cid)

    log.info("extra combos (snr_rising/trail): %d", len(extra_params))
    for i, params in enumerate(extra_params, 1):
        cid = combo_id(
            params["snr_min"], params["vol_mult"], params["twii_filter"],
            params["no_chase"], params["snr_rising"], params["trail"],
        )
        is_m, _ = run_combo(prices, params, IS_START, IS_END, "extra", "IS")
        oos_m, _ = run_combo(prices, params, OOS_START, OOS_END, "extra", "OOS")
        is_rows.append(is_m)
        oos_rows.append(oos_m)
        log.info(
            "extra [%d/%d] %s  OOS n=%d WR=%.1f%% exp=%.1f%% PF=%.2f",
            i, len(extra_params), cid,
            oos_m["trades"], oos_m["win_rate"] * 100, oos_m["expectancy"] * 100,
            oos_m["profit_factor"],
        )

    is_df = pd.DataFrame(is_rows)
    oos_df = pd.DataFrame(oos_rows)
    is_df.to_csv(REPORTS_DIR / "grid_is.csv", index=False, encoding="utf-8-sig")
    oos_df.to_csv(REPORTS_DIR / "grid_oos.csv", index=False, encoding="utf-8-sig")
    log.info("wrote grid CSVs in %.1fs", time.time() - t0)

    winner, reason = select_winner(oos_rows)
    constraints_met = passes_constraints(winner)
    chosen = params_of(winner)
    log.info("WINNER %s  (%s)", winner["combo_id"], reason)
    log.info("chosen params %s", chosen)
    (REPORTS_DIR / "chosen_params.json").write_text(
        json.dumps({"params": chosen, "reason": reason, "oos": {
            k: (None if isinstance(v, float) and (math.isnan(v) or math.isinf(v)) else v)
            for k, v in winner.items()
            if k not in ()
        }}, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    patch_config(chosen)

    # Full-sample v2 + v1, plus IS/OOS for both
    v2_spec = spec_from_params(chosen, name="breakout_v2")
    v1_spec = StrategySpec(
        name="breakout_v1",
        tp=v2_spec.tp, sl=v2_spec.sl, time_stop_days=v2_spec.time_stop_days,
        use_snr=True, kind="breakout",
    )

    log.info("full-sample breakout_v2")
    v2_full_res = run_universe(prices, v2_spec, INITIAL_CAPITAL, START_DATE, END_DATE)
    write_strategy_reports(v2_spec, v2_full_res)
    v2_full, v2_full_x = ew_from_results(v2_full_res)
    v2_full_summary = summarize_results(v2_full_res)
    v2_full_summary = pd.concat(
        [v2_full_summary, pd.DataFrame([v2_full, v2_full_x])], ignore_index=True
    )

    log.info("full-sample breakout_v1 (baseline)")
    v1_full_res = run_universe(prices, v1_spec, INITIAL_CAPITAL, START_DATE, END_DATE)
    write_strategy_reports(v1_spec, v1_full_res)
    v1_full, v1_full_x = ew_from_results(v1_full_res)
    v1_full_summary = summarize_results(v1_full_res)
    v1_full_summary = pd.concat(
        [v1_full_summary, pd.DataFrame([v1_full, v1_full_x])], ignore_index=True
    )

    log.info("IS/OOS windows for v1 and chosen v2")
    v1_is_res = run_universe(prices, v1_spec, INITIAL_CAPITAL, IS_START, IS_END)
    v1_oos_res = run_universe(prices, v1_spec, INITIAL_CAPITAL, OOS_START, OOS_END)
    v2_is_res = run_universe(prices, v2_spec, INITIAL_CAPITAL, IS_START, IS_END)
    v2_oos_res = run_universe(prices, v2_spec, INITIAL_CAPITAL, OOS_START, OOS_END)
    v1_is, _ = ew_from_results(v1_is_res)
    v1_oos, _ = ew_from_results(v1_oos_res)
    v2_is, _ = ew_from_results(v2_is_res)
    v2_oos, _ = ew_from_results(v2_oos_res)

    md = build_v2_md(
        winner, reason, constraints_met, is_rows, oos_rows,
        v1_is, v1_oos, v1_full, v1_full_x,
        v2_is, v2_oos, v2_full, v2_full_x,
        v2_full_summary, v1_full_summary,
    )
    (REPORTS_DIR / "v2_comparison.md").write_text(md, encoding="utf-8")
    log.info("wrote %s", REPORTS_DIR / "v2_comparison.md")

    print("\n======== breakout_v2 tuner ========")
    print("chosen:", winner["combo_id"], chosen)
    print("reason:", reason)
    print(
        f"OOS  v2 n={winner['trades']} WR={winner['win_rate']:.1%} "
        f"exp={winner['expectancy']:.1%} PF={winner['profit_factor']:.2f} "
        f"ret={winner['total_return']:.1%} dd={winner['max_dd']:.1%}"
    )
    print(
        f"OOS  v1 n={int(v1_oos['trades'])} WR={v1_oos['win_rate']:.1%} "
        f"exp={v1_oos['expectancy']:.1%} PF={v1_oos['profit_factor']:.2f} "
        f"ret={v1_oos['total_return']:.1%}"
    )
    print(
        f"FULL v2 n={int(v2_full['trades'])} WR={v2_full['win_rate']:.1%} "
        f"exp={v2_full['expectancy']:.1%} ret={v2_full['total_return']:.1%} "
        f"| no世紀 ret={v2_full_x['total_return']:.1%}"
    )
    print(
        f"FULL v1 n={int(v1_full['trades'])} WR={v1_full['win_rate']:.1%} "
        f"exp={v1_full['expectancy']:.1%} ret={v1_full['total_return']:.1%} "
        f"| no世紀 ret={v1_full_x['total_return']:.1%}"
    )
    print("===================================\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
