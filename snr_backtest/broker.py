"""Taiwan cash-equity costs and lot rounding.

Shares must be a multiple of lot_size (backtest 1000; paper 10).
If cash cannot buy one unit after commission, skip and keep cash.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Fill:
    shares: int
    price: float
    notional: float
    commission: float
    tax: float
    cash_delta: float  # negative for buy, positive for sell (net)


def commission_on(notional: float, rate: float, min_comm: float) -> float:
    if notional <= 0:
        return 0.0
    return max(notional * rate, min_comm)


def max_shares_for_cash(
    cash: float,
    price: float,
    lot_size: int,
    commission_rate: float,
    commission_min: float,
) -> int:
    """Largest multiple of lot_size whose (notional + buy commission) <= cash."""
    if cash <= 0 or price <= 0 or lot_size <= 0:
        return 0
    n_lots = int(cash // (price * lot_size))
    while n_lots > 0:
        shares = n_lots * lot_size
        notional = shares * price
        comm = commission_on(notional, commission_rate, commission_min)
        if notional + comm <= cash + 1e-8:
            return shares
        n_lots -= 1
    return 0


def buy_fill(
    cash: float,
    price: float,
    lot_size: int,
    commission_rate: float,
    commission_min: float,
) -> Fill | None:
    """All-in: spend as many lots as cash allows. None if cannot buy 1 lot."""
    shares = max_shares_for_cash(
        cash, price, lot_size, commission_rate, commission_min
    )
    if shares < lot_size:
        return None
    notional = shares * price
    comm = commission_on(notional, commission_rate, commission_min)
    return Fill(
        shares=shares,
        price=price,
        notional=notional,
        commission=comm,
        tax=0.0,
        cash_delta=-(notional + comm),
    )


def sell_fill(
    shares: int,
    price: float,
    commission_rate: float,
    commission_min: float,
    sell_tax_rate: float,
) -> Fill:
    """Close the whole position. Tax applies only on sells."""
    if shares <= 0 or price < 0:
        return Fill(0, price, 0.0, 0.0, 0.0, 0.0)
    notional = shares * price
    comm = commission_on(notional, commission_rate, commission_min)
    tax = notional * sell_tax_rate
    net = notional - comm - tax
    return Fill(
        shares=shares,
        price=price,
        notional=notional,
        commission=comm,
        tax=tax,
        cash_delta=net,
    )
