"""Map news heat → new-entry size. Never places orders. Never exits.

Macro heat (tariffs, Fed) only shrinks weight.
Hard lock (0 shares) is event-based: war-class phrases, named export-control
on that ticker, TWII crash, or RSS fail — not score >= 12.
"""
from __future__ import annotations

import csv
from pathlib import Path

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


def step_down(weight: float, n: int = 1) -> float:
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


def macro_size_weight(trend: str, lock_new: bool) -> float:
    if lock_new:
        return 0.0
    return {
        "cool": 0.20,
        "cooling": 0.10,
        "hot": 0.05,
        "severe": 0.02,
    }.get(str(trend or "cool"), 0.20)


def apply_name(weight: float, name_trend: str, name_lock: bool) -> float:
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
    """Cash cap for one new name. weight already includes news sizing."""
    if cash <= 0 or equity <= 0 or weight <= 0:
        return 0.0
    w = min(float(weight), float(max_weight))
    slots = max(1, int(slots_left))
    return float(min(cash, equity * w, cash / slots))


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
