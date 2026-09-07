"""Taiwan cash-equity costs and lot rounding.

Shares must be a multiple of lot_size (backtest 1000; paper preferred 5).
If cash cannot buy one unit after commission, skip and keep cash.
Paper callers may retry with lot_size=1 (true odd lot) via try_buy_fill.
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


def tw_tick(price: float) -> float:
    """TWSE/TPEx listed tick. Not warrants / ETFs with special bands."""
    p = abs(float(price))
    if p < 10:
        return 0.01
    if p < 50:
        return 0.05
    if p < 100:
        return 0.1
    if p < 500:
        return 0.5
    if p < 1000:
        return 1.0
    if p < 5000:
        return 5.0
    return 10.0


def round_tick(price: float) -> float:
    t = tw_tick(price)
    if t <= 0:
        return float(price)
    return round(float(price) / t) * t


def limit_up_price(prev_close: float) -> float:
    return round_tick(float(prev_close) * 1.10)


def limit_down_price(prev_close: float) -> float:
    return round_tick(float(prev_close) * 0.90)


def at_limit_up(open_px: float, prev_close: float | None) -> bool:
    if not prev_close or prev_close <= 0 or open_px <= 0:
        return False
    cap = limit_up_price(prev_close)
    return abs(float(open_px) - cap) <= tw_tick(open_px) * 0.51 + 1e-9


def at_limit_down(open_px: float, prev_close: float | None) -> bool:
    if not prev_close or prev_close <= 0 or open_px <= 0:
        return False
    floor = limit_down_price(prev_close)
    return abs(float(open_px) - floor) <= tw_tick(open_px) * 0.51 + 1e-9


def commission_on(notional: float, rate: float, min_comm: float) -> float:
    if notional <= 0:
        return 0.0
    return max(notional * rate, min_comm)


def buy_cost(
    shares: int,
    price: float,
    commission_rate: float,
    commission_min: float,
) -> float:
    """Cash needed to buy `shares` at price including buy commission."""
    if shares <= 0 or price <= 0:
        return float("inf")
    notional = float(shares) * float(price)
    return notional + commission_on(notional, commission_rate, commission_min)


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



def try_buy_fill(
    cash: float,
    price: float,
    preferred_lot: int,
    commission_rate: float,
    commission_min: float,
    fallback_lot: int = 1,
) -> tuple[Fill | None, int]:
    """Try preferred_lot first; if unaffordable, retry fallback_lot (paper: 5 then 1).

    Returns (fill, lot_size_used). fill is None and lot 0 if even 1 share is too costly.
    """
    fill = buy_fill(cash, price, preferred_lot, commission_rate, commission_min)
    if fill is not None:
        return fill, int(preferred_lot)
    if fallback_lot > 0 and int(fallback_lot) != int(preferred_lot):
        fill = buy_fill(cash, price, fallback_lot, commission_rate, commission_min)
        if fill is not None:
            return fill, int(fallback_lot)
    return None, 0


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



if __name__ == "__main__":
    # expensive name under tiny budget: 5-lot fails, 1-lot ok
    px = 2500.0
    budget = 3000.0
    rate, mn = 0.001425, 20.0
    f5 = buy_fill(budget, px, 5, rate, mn)
    assert f5 is None
    f1 = buy_fill(budget, px, 1, rate, mn)
    assert f1 is not None and f1.shares == 1
    fill, lot = try_buy_fill(budget, px, 5, rate, mn, fallback_lot=1)
    assert fill is not None and lot == 1 and fill.shares >= 1
    # still cannot afford 1 share
    fill2, lot2 = try_buy_fill(100.0, px, 5, rate, mn, fallback_lot=1)
    assert fill2 is None and lot2 == 0
    assert buy_cost(1, px, rate, mn) > 100.0
    # normal affordable 5-lot path
    fill3, lot3 = try_buy_fill(50_000.0, 100.0, 5, rate, mn, fallback_lot=1)
    assert fill3 is not None and lot3 == 5 and fill3.shares >= 5
    print("broker self-check ok")
