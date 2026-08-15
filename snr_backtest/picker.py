"""Rank breakout+SNR candidates and fill empty portfolio slots.

Among names with a valid entry signal today:
- Rank by SNR_20 desc, then 20-day relative strength vs ^TWII
- Keep existing holdings until their exit; only fill empty slots
- Do not add a name already held (or already pending)
- Cap at max_positions (default 5)
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd


def rank_candidates(
    rows: list[dict],
    held: Iterable[str],
    pending: Iterable[str],
    max_new: int,
) -> list[dict]:
    """Return top `max_new` new names, already sorted.

    Each row: ticker, name, snr, rs, close (extra keys passed through).
    """
    held_set = set(held)
    pending_set = set(pending)
    fresh = [
        r for r in rows
        if r.get("ticker") not in held_set and r.get("ticker") not in pending_set
    ]
    fresh.sort(
        key=lambda r: (
            -float(r.get("snr") or 0.0),
            -float(r.get("rs") or 0.0),
            str(r.get("ticker") or ""),
        )
    )
    if max_new <= 0:
        return []
    return fresh[:max_new]


def format_rank_table(rows: list[dict], picked: set[str] | None = None) -> str:
    if not rows:
        return "(no signals)"
    picked = picked or set()
    lines = [
        f"{'pick':<4} {'ticker':<12} {'name':<10} {'snr':>7} {'rs_20':>8} {'close':>10}"
    ]
    for r in rows:
        mark = "*" if r["ticker"] in picked else ""
        snr = r.get("snr")
        rs = r.get("rs")
        close = r.get("close")
        lines.append(
            f"{mark:<4} {r['ticker']:<12} {str(r.get('name', '')):<10} "
            f"{float(snr or 0):7.4f} {float(rs or 0):8.4f} {float(close or 0):10.2f}"
        )
    return "\n".join(lines)
