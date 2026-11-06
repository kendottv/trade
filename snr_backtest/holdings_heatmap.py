"""持股熱力圖顯示用純計算。不碰真實 DB / 報價 / 下單。"""
from __future__ import annotations
from typing import Any


def valid_mv(mv: Any) -> bool:
    try:
        v = float(mv)
        return v == v and v > 0
    except (TypeError, ValueError):
        return False


def holdings_share(positions: list[dict], mv_key: str = "mv") -> dict[str, float]:
    """占該帳戶有效正市值比例（不含現金）。"""
    total = sum(float(p[mv_key]) for p in positions if valid_mv(p.get(mv_key)))
    if total <= 0:
        return {}
    return {
        str(p.get("code") or p.get("ticker") or ""): float(p[mv_key]) / total
        for p in positions
        if valid_mv(p.get(mv_key))
    }


def day_change(last: Any, prev_close: Any) -> float | None:
    try:
        l, p = float(last), float(prev_close)
        if l != l or p != p or p <= 0:
            return None
        return l / p - 1
    except (TypeError, ValueError):
        return None


def buy_pnl_pct(last: Any, avg: Any) -> float | None:
    try:
        l, a = float(last), float(avg)
        if l != l or a != a or a <= 0:
            return None
        return l / a - 1
    except (TypeError, ValueError):
        return None


def group_by_industry(positions: list[dict]) -> dict[str, list[dict]]:
    g: dict[str, list[dict]] = {}
    for p in positions:
        ind = str(p.get("industry") or "").strip() or "未知"
        g.setdefault(ind, []).append(p)
    return g


def squarify(values: list[float], x: float, y: float, w: float, h: float) -> list[dict]:
    """Squarified treemap。回傳 [{'i': index, 'x','y','w','h'}]。"""
    if not values or w <= 0 or h <= 0:
        return []
    total = sum(values)
    if total <= 0:
        return []
    areas = [v / total * w * h for v in values]
    return _squarify(areas, x, y, w, h, list(range(len(values))))


def _squarify(areas: list[float], x: float, y: float, w: float, h: float, idxs: list[int]) -> list[dict]:
    if not areas:
        return []
    if len(areas) == 1:
        return [{"i": idxs[0], "x": x, "y": y, "w": w, "h": h}]
    short = min(w, h)
    row: list[float] = []
    row_idxs: list[int] = []
    i = 0
    while i < len(areas):
        candidate = row + [areas[i]]
        if not row or _worst(row, short) >= _worst(candidate, short):
            row.append(areas[i])
            row_idxs.append(idxs[i])
            i += 1
        else:
            break
    row_sum = sum(row)
    if w >= h:
        rw = row_sum / h
        out = []
        cy = y
        for a, ii in zip(row, row_idxs):
            rh = a / rw
            out.append({"i": ii, "x": x, "y": cy, "w": rw, "h": rh})
            cy += rh
        out.extend(_squarify(areas[i:], x + rw, y, w - rw, h, idxs[i:]))
    else:
        rh = row_sum / w
        out = []
        cx = x
        for a, ii in zip(row, row_idxs):
            rw = a / rh
            out.append({"i": ii, "x": cx, "y": y, "w": rw, "h": rh})
            cx += rw
        out.extend(_squarify(areas[i:], x, y + rh, w, h - rh, idxs[i:]))
    return out


def _worst(row: list[float], short: float) -> float:
    if not row:
        return float("inf")
    s = sum(row)
    m = max(row)
    n = min(row)
    return max((short * short * m) / (s * s), (s * s) / (short * short * n))


def layout_tiles(positions: list[dict], width: float = 800, height: float = 400, mv_key: str = "mv") -> list[dict]:
    """回傳每個有效持股的矩形（含 code、share、x/y/w/h、area）。無效者不包含。"""
    valid = [p for p in positions if valid_mv(p.get(mv_key))]
    if not valid:
        return []
    shares = holdings_share(valid, mv_key)
    values = [float(p[mv_key]) for p in valid]
    rects = squarify(values, 0, 0, width, height)
    out = []
    for r in rects:
        p = valid[r["i"]]
        code = str(p.get("code") or p.get("ticker") or "")
        out.append({
            "code": code,
            "share": shares.get(code, 0.0),
            "x": r["x"], "y": r["y"], "w": r["w"], "h": r["h"],
            "area": r["w"] * r["h"],
            "pos": p,
        })
    return out
