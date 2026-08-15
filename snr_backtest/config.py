"""Backtest configuration: universe, costs, dates, SNR thresholds."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"

# Keep this universe exactly (10 names + index).
TICKERS = {
    "2330.TW": "台積電",
    "3035.TW": "致新",
    "5314.TWO": "世紀",
    "6197.TW": "佳必琪",
    "6217.TWO": "中探針",
    "2360.TW": "致茂電子",
    "2404.TW": "漢唐",
    "3037.TW": "欣興電子",
    "2449.TW": "京元電子",
    "3044.TW": "健鼎科技",
}

INDEX_TICKER = "^TWII"  # used by breakout_v2 twii_filter; v1 does NOT use TWII
INDEX_NAME = "台灣加權"

# 世紀 is a lottery runner — always also report equal-weight with it removed.
LOTTERY_TICKER = "5314.TWO"

# Main sample: 5 years ending 2026-08-13. Extra history before START_DATE is SMA/SNR warmup.
# END_DATE is the *backtest* sample end only. Paper live/alert load with end_date=None.
START_DATE = "2021-08-13"
END_DATE = "2026-08-13"
WARMUP_START = "2020-08-01"
# Optional 3-year slice reported in comparison.md (same cached prices, separate run).
SLICE_3Y_START = "2023-08-13"

# Walk-forward windows for tune.py. Decision metric is OOS, not IS.
IS_START = "2021-08-13"
IS_END = "2024-08-12"
OOS_START = "2024-08-13"
OOS_END = "2026-08-13"

INITIAL_CAPITAL = 1_000_000.0
LOT_SIZE = 1000  # 回測：1 張
# 紙上零股單位（10／50／100 都可以）。買得到幾單位就買幾單位。
PAPER_LOT_SIZE = 10
# 單檔最多佔組合權益的比例。當天只出 1 檔訊號也不把現金 all-in。
PAPER_MAX_WEIGHT = 0.20

# Taiwan cash-equity costs (applied on notional).
COMMISSION_RATE = 0.001425  # 0.1425% each side
COMMISSION_MIN = 20.0  # NT$ floor
SELL_TAX_RATE = 0.003  # 0.3% sell tax

# Kaufman efficiency ratio / 訊噪比
SNR_N = 20
BREAKOUT_SNR_MIN = 0.40  # v1: only take breakouts in a clean trend
PULLBACK_SNR_MAX = 0.25  # only take pullbacks in a choppy regime

# Strategy parameters (shared TP/SL/time-stop; do not change lot/cost/next-bar)
BREAKOUT_LOOKBACK = 20
BREAKOUT_TP = 0.25
BREAKOUT_SL = 0.20
BREAKOUT_TIME_STOP_DAYS = 3

PULLBACK_SMA_TREND = 60
PULLBACK_SMA_FAST = 20
PULLBACK_BAND_LO = 0.97
PULLBACK_BAND_HI = 1.01
PULLBACK_TP = 0.08
PULLBACK_SL = 0.04

# breakout_v2 defaults — OOS grid winner (see reports/v2_comparison.md).
BREAKOUT_V2_SNR_MIN = 0.40
BREAKOUT_V2_SNR_RISING = False
BREAKOUT_V2_VOL_MULT = 0.0  # 0 = volume filter off
BREAKOUT_V2_TWII_FILTER = True
BREAKOUT_V2_NO_CHASE = False
BREAKOUT_V2_CHASE_MULT = 1.08
BREAKOUT_V2_TRAIL = True
BREAKOUT_V2_TRAIL_ARM = 0.12  # arm trail once unrealized >= 12% vs fill
BREAKOUT_V2_TRAIL_LOOKBACK = 15  # then exit next open if close < prior 15-day low
BREAKOUT_V2_SNR_SMA = 5
TWII_SMA = 60
