"""Configuration constants for strategy combination research.
All values are fixed per the approved specification. Paths are relative
to the repository root unless overridden by CLI in later parts.
"""
from pathlib import Path

# Repository root is two levels above this file (research/strategy_combo/config.py)
REPO_ROOT = Path(__file__).resolve().parents[2]

# Default NN3 output directory (sibling of the repo on the development machine)
DEFAULT_NN_OUT_DIR = REPO_ROOT / ".." / "trade_NN" / "out"

# Backup used only for comparison in the report
DEFAULT_NN_BACKUP_DIR = REPO_ROOT / ".." / "trade_NN" / "out_backup_20261112"

# TWII path inside the repo
TWII_PATH = REPO_ROOT / "snr_backtest" / "data" / "TWII.csv"

# Data directory for this research module (yfinance caches only)
DATA_DIR = Path(__file__).resolve().parent / "data"

# Membership intervals (point-in-time universe)
MEMBERSHIP_CSV = Path(__file__).resolve().parent / "inputs" / "tw50_membership_intervals.csv"

# TEJ manifest (committed, no prices)
TEJ_MANIFEST_CSV = Path(__file__).resolve().parent / "inputs" / "tej_manifest.csv"

# TEJ raw files (gitignored)
TEJ_INPUT_DIR = Path(__file__).resolve().parent / "inputs" / "tej"
TEJ_PRICES_A = TEJ_INPUT_DIR / "tej_prices_a.txt"
TEJ_PRICES_B = TEJ_INPUT_DIR / "tej_prices_b.txt"

# TEJ-only codes (never yfinance, never mix)
TEJ_STOCK_CODES = ("2311", "2325", "3474", "3697", "2823", "2888")

# ETFs (yfinance, .TW)
ETF_CODES = ("0050", "00632R")

# Main strategy column name in portfolio_monthly.csv
MAIN_STRATEGY_COL = "Top20 等權 緩衝40 產業≤30%"

# Transaction cost parameters (AC-7)
FEE_RATE = 0.001425          # 0.1425% each side
FEE_MIN_TWD = 20.0           # minimum commission in TWD
STOCK_TAX_RATE = 0.003       # 0.3% sell-side for individual stocks
ETF_TAX_RATE = 0.001         # 0.1% sell-side for ETFs (0050, 00632R)
SLIPPAGE_RATE = 0.001        # 0.1% each side

# Assumed principal (documented in README in later parts)
DEFAULT_PRINCIPAL_TWD = 1_000_000.0

# CTA parameters (fixed, no optimization)
CTA_MA_WINDOW = 200

# Mean-reversion B parameters (fixed hypotheses)
B_MA_SHORT = 20
B_STD_MULT = 2.0
B_MA_LONG = 200
B_MAX_HOLD_DAYS = 10
B_MAX_POSITIONS = 10
B_WEIGHT_PER_POSITION = 0.10

# ETF symbols (Yahoo format) — kept for compatibility
ETF_SYMBOLS = {"0050.TW", "00632R.TW"}
