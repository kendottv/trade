"""Map news heat → today's new-buy budget pool + per-name share.

Macro heat (tariffs, Fed) only sets the SIZE OF TODAY'S BUDGET POOL for new
buys — not a flat per-name equity weight alone:
  pool = deployable_cash * macro_pool_fraction(trend, lock_new)

Within that pool, allocate across today's new candidate buys by EACH NAME's
own news heat (clean→more, noisy→less; lock→0). Paper sizing tries PAPER_LOT_SIZE then falls back to 1 share; skip if even 1 share (+fees) exceeds alloc/cash.

Hard lock (0 shares / empty pool) is event-based: war-class phrases, named
export-control on that ticker, TWII crash, or RSS fail — not score >= 12.

Never places orders. Never exits.
"""
from __future__ import annotations

import csv
from pathlib import Path

# Macro → fraction of deployable cash that becomes today's new-buy pool.
MACRO_POOL_FRACTION = {
    "cool": 0.20,
    "cooling": 0.10,
    "hot": 0.05,
    "severe": 0.02,
}

# Relative shares inside the pool (not equity weights). lock → 0 elsewhere.
# cool > cooling(warm) > hot > severe; unknown treated cautiously mid.
NAME_SHARE = {
    "cool": 4.0,
    "cooling": 2.0,
    "warm": 2.0,
    "hot": 1.0,
    "severe": 0.5,
    "unknown": 1.0,
}

# Legacy ladder kept for step_down / old pending fallback only.
STEPS = (0.20, 0.10, 0.05, 0.02)

SIZE_JOURNAL_COLS = [
    "logged_at", "session", "ticker", "name",
    "macro_trend", "macro_heat", "macro_weight",
    "war_lock", "old_switch_would_block", "lock_new",
    "name_heat", "name_trend", "name_lock",
    "target_weight", "shares", "budget", "note",
]

# +3 phrases in news_risk.WEIGHTS — event lock, not a score cutoff.
WAR_PHRASES = (
    "invasion",
    "blockade",
    "missile",
    "war",
    "戰爭",
    "導彈",
    "封鎖",
    "入侵",
)

# Per-name lock only if the title also mentions that company.
NAME_LOCK_PHRASES = (
    "出口管制",
    "禁運",
    "制裁",
    "export control",
    "embargo",
    "sanction",
)


def macro_pool_fraction(trend: str, lock_new: bool) -> float:
    """Fraction of deployable cash for today's new-buy pool."""
    if lock_new:
        return 0.0
    return float(MACRO_POOL_FRACTION.get(str(trend or "cool"), 0.20))


def macro_size_weight(trend: str, lock_new: bool) -> float:
    """Alias: news_risk.size_weight stores the macro pool fraction."""
    return macro_pool_fraction(trend, lock_new)


def name_share_weight(name_trend: str, name_lock: bool) -> float:
    """Relative weight inside the pool. lock → 0."""
    if name_lock:
        return 0.0
    t = str(name_trend or "cool").strip().lower()
    if not t:
        t = "cool"
    return float(NAME_SHARE.get(t, NAME_SHARE["cool"]))


def compute_pool(deployable_cash: float, trend: str, lock_new: bool) -> float:
    return max(0.0, float(deployable_cash)) * macro_pool_fraction(trend, lock_new)


def allocate_pool(
    pool: float,
    candidates: list[dict],
    *,
    equity: float = 0.0,
    max_weight: float = 0.20,
) -> list[dict]:
    """Split pool across candidates by name heat.

    Each candidate dict needs name_trend / name_lock (others passed through).
    Returns new dicts with: share_w, share, budget, target_weight (= share of pool).
    Single-name cap: min(budget, equity * max_weight) when equity > 0.
    """
    pool = max(0.0, float(pool))
    scored: list[dict] = []
    for c in candidates:
        row = dict(c)
        w = name_share_weight(str(row.get("name_trend") or "cool"), bool(row.get("name_lock")))
        row["share_w"] = w
        scored.append(row)

    total = sum(float(r["share_w"]) for r in scored)
    out: list[dict] = []
    cap = float(equity) * float(max_weight) if equity and max_weight else None
    for r in scored:
        w = float(r["share_w"])
        if pool <= 0 or total <= 0 or w <= 0:
            share = 0.0
            budget = 0.0
        else:
            share = w / total
            budget = pool * share
            if cap is not None and cap > 0:
                budget = min(budget, cap)
        r["share"] = share
        r["budget"] = float(budget)
        r["target_weight"] = float(share)  # share of today's pool
        out.append(r)
    return out


def step_down(weight: float, n: int = 1) -> float:
    """Legacy ladder helper (kept for tests / old paths)."""
    if weight <= 0:
        return 0.0
    if n <= 0:
        return float(weight)
    try:
        i = STEPS.index(float(weight))
    except ValueError:
        i = 0
        for j, s in enumerate(STEPS):
            if weight >= s:
                i = j
                break
    return float(STEPS[min(i + n, len(STEPS) - 1)])


def apply_name(weight: float, name_trend: str, name_lock: bool) -> float:
    """Legacy: step down macro equity-weight by name heat. Prefer allocate_pool."""
    if name_lock or weight <= 0:
        return 0.0
    t = str(name_trend or "cool")
    if t == "hot":
        return step_down(weight, 1)
    if t == "severe":
        return step_down(weight, 2)
    return float(weight)


def target_budget(
    cash: float,
    equity: float,
    slots_left: int,
    weight: float,
    max_weight: float,
) -> float:
    """Legacy cash cap for one new name (equity * weight). Prefer stored alloc."""
    if cash <= 0 or equity <= 0 or weight <= 0:
        return 0.0
    w = min(float(weight), float(max_weight))
    slots = max(1, int(slots_left))
    return float(min(cash, equity * w, cash / slots))


def resolve_fill_budget(
    *,
    stored_budget: float | None,
    target_weight: float | None,
    cash: float,
    equity: float,
    slots_left: int,
    max_weight: float,
) -> float:
    """Prefer queued target_budget; fall back to legacy equity*weight for old pending."""
    if stored_budget is not None:
        b = float(stored_budget)
        if b <= 0:
            return 0.0
        cap = float(equity) * float(max_weight) if equity > 0 else float(cash)
        return float(min(b, float(cash), cap if cap > 0 else float(cash)))
    w = float(max_weight if target_weight is None else target_weight)
    if w <= 0:
        return 0.0
    return target_budget(float(cash), float(equity), slots_left, w, float(max_weight))


def format_size_note(
    *,
    pool: float,
    macro_trend: str,
    macro_frac: float,
    name_trend: str,
    name_heat,
    share: float,
    alloc: float,
) -> str:
    heat_s = "" if name_heat in (None, "") else str(name_heat)
    return (
        f"pool={pool:.0f} macro={macro_trend}/{macro_frac:.0%} "
        f"name={name_trend}/{heat_s} share={share:.0%} alloc={alloc:.0f}"
    )


def append_size_journal(row: dict, root: Path | None = None) -> None:
    from config import ROOT

    path = (Path(root) if root else ROOT / "paper") / "size_journal.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    new = (not path.exists()) or path.stat().st_size == 0
    with path.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SIZE_JOURNAL_COLS)
        if new:
            w.writeheader()
        w.writerow({c: row.get(c, "") for c in SIZE_JOURNAL_COLS})


if __name__ == "__main__":
    # self-check: pool + name allocation
    assert macro_pool_fraction("cool", False) == 0.20
    assert macro_pool_fraction("severe", False) == 0.02
    assert macro_pool_fraction("hot", True) == 0.0
    assert name_share_weight("cool", False) > name_share_weight("hot", False)
    assert name_share_weight("hot", False) > name_share_weight("severe", False)
    assert name_share_weight("cool", True) == 0.0

    pool = compute_pool(1_000_000.0, "cool", False)
    assert abs(pool - 200_000.0) < 1e-6

    rows = allocate_pool(
        pool,
        [
            {"ticker": "A", "name_trend": "cool", "name_lock": False},
            {"ticker": "B", "name_trend": "hot", "name_lock": False},
            {"ticker": "C", "name_trend": "cool", "name_lock": True},
        ],
        equity=1_000_000.0,
        max_weight=0.20,
    )
    by = {r["ticker"]: r for r in rows}
    assert by["C"]["budget"] == 0.0
    assert by["A"]["budget"] > by["B"]["budget"]
    # cool:4 + hot:1 = 5; A gets 4/5 of pool, B 1/5; both under 20% equity cap
    assert abs(by["A"]["budget"] - 160_000.0) < 1e-6
    assert abs(by["B"]["budget"] - 40_000.0) < 1e-6
    assert abs(by["A"]["share"] + by["B"]["share"] - 1.0) < 1e-9

    # severe macro → tiny pool
    p2 = compute_pool(1_000_000.0, "severe", False)
    assert abs(p2 - 20_000.0) < 1e-6

    # fill prefers stored budget
    b = resolve_fill_budget(
        stored_budget=50_000.0,
        target_weight=0.20,
        cash=80_000.0,
        equity=1_000_000.0,
        slots_left=3,
        max_weight=0.20,
    )
    assert abs(b - 50_000.0) < 1e-6

    # single-name cap
    one = allocate_pool(
        500_000.0,
        [{"ticker": "X", "name_trend": "cool", "name_lock": False}],
        equity=1_000_000.0,
        max_weight=0.20,
    )
    assert abs(one[0]["budget"] - 200_000.0) < 1e-6  # capped at 20% equity

    note = format_size_note(
        pool=200_000, macro_trend="cool", macro_frac=0.20,
        name_trend="hot", name_heat=7, share=0.2, alloc=40_000,
    )
    assert "pool=200000" in note and "alloc=40000" in note


    # high-priced name: 5-lot fails under severe-sized budget, 1-lot ok
    from broker import buy_cost, try_buy_fill
    px, budget = 5000.0, 20_000.0  # severe 2% of 1M
    assert buy_cost(5, px, 0.001425, 20.0) > budget
    assert buy_cost(1, px, 0.001425, 20.0) < budget
    fill, lot = try_buy_fill(budget, px, 5, 0.001425, 20.0, fallback_lot=1)
    assert fill is not None and lot == 1 and fill.shares >= 1
    # 1 share still too expensive → skip
    fill2, lot2 = try_buy_fill(1_000.0, px, 5, 0.001425, 20.0, fallback_lot=1)
    assert fill2 is None and lot2 == 0

    print("size_risk self-check ok")
