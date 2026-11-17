"""Transaction cost calculations (AC-7).

Fee: 0.1425% each side, minimum 20 TWD.
Tax: only on sell; 0.3% for stocks, 0.1% for ETFs (0050, 00632R).
Slippage: 0.1% each side.
"""
from .config import (
    FEE_RATE,
    FEE_MIN_TWD,
    STOCK_TAX_RATE,
    ETF_TAX_RATE,
    SLIPPAGE_RATE,
    ETF_SYMBOLS,
)


def is_etf(symbol: str) -> bool:
    """Return True if the symbol is treated as an ETF for tax purposes."""
    s = str(symbol).upper()
    return s in ETF_SYMBOLS or s.replace(".TW", "") in {"0050", "00632R"}


def compute_side_cost(notional: float, is_buy: bool, symbol: str) -> float:
    """Return the absolute TWD cost for one side of a trade.

    Parameters
    ----------
    notional : float
        Absolute value of the trade in TWD.
    is_buy : bool
        True for buy, False for sell.
    symbol : str
        Ticker used to decide ETF vs stock tax.

    Returns
    -------
    float
        Total cost in TWD (fee + tax if sell + slippage).
    """
    if notional <= 0:
        return 0.0

    fee = max(notional * FEE_RATE, FEE_MIN_TWD)

    tax = 0.0
    if not is_buy:
        tax_rate = ETF_TAX_RATE if is_etf(symbol) else STOCK_TAX_RATE
        tax = notional * tax_rate

    slippage = notional * SLIPPAGE_RATE

    return fee + tax + slippage


def cost_as_return_drag(notional: float, is_buy: bool, symbol: str, position_value: float) -> float:
    """Convert absolute cost into a return drag on the position."""
    if position_value <= 0:
        return 0.0
    return compute_side_cost(notional, is_buy, symbol) / position_value
