"""News heat switch — a small rule model, not an LLM and not a stock picker.

Only answers: can we open NEW paper positions today?

Pipeline
  1. Google News RSS (5 queries) → titles
  2. Dedup: drop publisher suffix, same story once
  3. Weighted heat per unique title (strong words > generic 關稅).
     Among hits, a shorter phrase is dropped if it sits inside a longer hit
     (order of WEIGHTS does not matter). English uses whole-word match.
  4. Cap each title so eight near-copies cannot explode the score
  5. 21:30 store heat; next 08:30 compare trend
  6. TWII 1-day / 3-day crash still pauses
  7. If RSS fetch fails entirely, treat as unknown risk and pause
     (fail-safe, not fail-open)

Decision (news only; price applied after)
  cool     morning heat < HOT          → allow
  cooling  still warm but dropped enough and not SEVERE → allow
  hot      warm and not improving      → pause
  severe   morning heat >= SEVERE      → pause even if cooling a bit
  unknown  RSS fetch failed entirely   → pause (no signal, don't assume calm)
  no 21:30 yet                         → morning only (cool vs hot)

Replay: price stress only (RSS has no historical same-day headlines).
Existing positions still use TP/SL/trail. Not a broker.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

from config import ROOT

TAIPEI = timezone(timedelta(hours=8))
PAPER = ROOT / "paper"
RISK_PATH = PAPER / "news_risk.json"
SNAPSHOT_2130_PATH = PAPER / "news_snapshot_2130.json"
JOURNAL_PATH = PAPER / "news_journal.csv"

JOURNAL_COLS = [
    "logged_at", "session", "slot", "algo",
    "heat", "n_unique", "n_raw", "fetch_ok", "fetch_total",
    "trend", "news_allow", "allow_new_entries", "would_flat",
    "prev_score", "prev_session",
    "twii_d1", "twii_d3", "price_pause",
    "cash", "equity", "n_positions", "holdings",
    "reason",
]

UA = "Mozilla/5.0 (compatible; TWPaperRisk/1.0)"

QUERIES = [
    "川普 關稅 台股",
    "台積電 制裁 關稅",
    "台海 衝突",
    "Trump tariff Taiwan semiconductor",
    "聯準會 升息 台股",
]

# Phrase order does not matter: headline_heat() keeps the longest hit and
# drops a shorter one that sits inside it ("取消關稅" wins over "關稅").
# English tokens use whole-word match so "war" ≠ "warning".
# Positive weight = heat (risk). Negative = cooling.
WEIGHTS: list[tuple[str, int]] = [
    ("全面性關稅", 2),
    ("出口管制", 2),
    ("取消關稅", -2),
    ("pause tariff", -2),
    ("export control", 2),
    ("exemption", -2),
    ("ceasefire", -2),
    ("invasion", 3),
    ("blockade", 3),
    ("sanction", 2),
    ("embargo", 2),
    ("hawkish", 1),
    ("selloff", 2),
    ("missile", 3),
    ("dovish", -2),
    ("tariff", 1),
    ("truce", -2),
    ("trade deal", -1),
    ("peace deal", -1),
    ("war", 3),
    ("加徵", 2),
    ("制裁", 2),
    ("禁運", 2),
    ("戰爭", 3),
    ("衝突", 2),
    ("導彈", 3),
    ("封鎖", 3),
    ("入侵", 3),
    ("衰退", 2),
    ("恐慌", 2),
    ("暴跌", 2),
    ("崩跌", 2),
    ("升息", 1),
    ("鷹派", 1),
    ("降息", -2),
    ("協議", -1),
    ("休戰", -2),
    ("豁免", -2),
    ("利多", -1),
    ("鴿派", -2),
    ("暫緩", -1),
    ("taco", -2),
    ("踩剎車", -2),
    ("談妥", -1),
    ("降至", -1),
    ("調降", -1),
    ("降低關稅", -2),
    ("關稅", 1),
]

# Bare 關稅/tariff is noise when the same title is about a cut, pause, or deal.
_TARIFF_GENERIC = ("關稅", "tariff")
_TARIFF_COOL = (
    "taco",
    "踩剎車",
    "降至",
    "調降",
    "降低關稅",
    "取消關稅",
    "pause tariff",
    "豁免",
    "暫緩",
    "談妥",
    "協議",
    "違憲",
    "exemption",
    "trade deal",
)

# Explainer / clickbait: no event, do not score.
_COMMENTARY = (
    "一文看",
    "一文看懂",
    "有哪些風險",
    "有哪些多重風險",
    "什麼是關稅",
)

TITLE_HEAT_CAP = 4  # one headline cannot add more than this
HOT = 6  # below this = cool enough to open
SEVERE = 12  # still this hot → stay closed even if cooling
COOLING_DROP = 3  # need at least this much overnight drop to count as cooling
D1_PAUSE = -0.015
D3_PAUSE = -0.03

try:
    from ui_settings import load_news_overlay

    _news_ov = load_news_overlay()
    if "HOT" in _news_ov:
        HOT = int(_news_ov["HOT"])
    if "SEVERE" in _news_ov:
        SEVERE = int(_news_ov["SEVERE"])
    if "COOLING_DROP" in _news_ov:
        COOLING_DROP = int(_news_ov["COOLING_DROP"])
except Exception:
    pass

_PUBLISHER = re.compile(r"\s+[-–—|]\s+\S+\s*$")
_NOISE = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)


def _now_iso() -> str:
    return datetime.now(TAIPEI).strftime("%Y-%m-%d %H:%M:%S%z")


def normalize_title(title: str) -> str:
    """Drop site name after the last dash so copies from different outlets match."""
    t = re.sub(r"\s+", " ", (title or "")).strip()
    t = _PUBLISHER.sub("", t).strip()
    return t.lower()


def title_key(title: str) -> str:
    return _NOISE.sub("", normalize_title(title))


def _is_ascii_phrase(phrase: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9 \-]+", phrase.lower()))


def phrase_in_title(text: str, phrase: str) -> bool:
    """Chinese: substring. English: whole words, optional trailing s (tariffs)."""
    p = phrase.lower()
    if _is_ascii_phrase(p):
        return re.search(r"\b" + re.escape(p) + r"s?\b", text) is not None
    return p in text


def headline_heat(title: str) -> tuple[int, list[str], list[str]]:
    """Weighted heat of one title. Returns (capped_heat, off_words, on_words).

    Collect every hit, then drop a phrase that is contained in a longer hit.
    WEIGHTS list order is ignored.
    """
    key = normalize_title(title)
    if any(c in key for c in _COMMENTARY):
        return 0, [], []
    found: list[tuple[str, int]] = []
    for phrase, w in WEIGHTS:
        if phrase_in_title(key, phrase):
            found.append((phrase, w))
    cool_tariff = any(phrase_in_title(key, c) for c in _TARIFF_COOL)
    if cool_tariff:
        found = [(p, w) for p, w in found if p.lower() not in _TARIFF_GENERIC]
    kept: list[tuple[str, int]] = []
    for phrase, w in found:
        p = phrase.lower()
        if any(p != other.lower() and p in other.lower() for other, _ in found):
            continue
        kept.append((phrase, w))
    raw = 0
    off: list[str] = []
    on: list[str] = []
    for phrase, w in kept:
        raw += w
        if w > 0:
            off.append(phrase)
        else:
            on.append(phrase)
    heat = max(-TITLE_HEAT_CAP, min(TITLE_HEAT_CAP, raw))
    return heat, off, on


def score_titles(titles: list[str]) -> dict:
    """Dedup + weight. news_score is total heat (compat name for paper_daily)."""
    seen: set[str] = set()
    unique: list[str] = []
    heat = 0
    off_hits: list[str] = []
    on_hits: list[str] = []
    for t in titles:
        k = title_key(t)
        if not k or k in seen:
            continue
        seen.add(k)
        unique.append(t)
        h, off, on = headline_heat(t)
        heat += h
        # Classify by net heat, not "any risk word". A deal/cut title can
        # contain 關稅 and 協議; it must not sit in both lists.
        if h > 0:
            off_hits.append(t)
        elif h < 0:
            on_hits.append(t)
    return {
        "news_score": int(heat),
        "n_unique": len(unique),
        "n_raw": len(titles),
        "off_headlines": off_hits[:8],
        "on_headlines": on_hits[:8],
        "unique_titles": unique[:40],
    }


# Metaphor / clickbait that contains a war-class token but is not kinetic war.
# 關稅戰 ≠ 戰爭；封鎖消息 ≠ 海上封鎖。
_WAR_METAPHOR_ZH = (
    "關稅戰",
    "貿易戰",
    "價格戰",
    "匯率戰",
    "晶片戰",
    "半導體戰",
    "電池戰",
    "補貼戰",
    "宣傳戰",
    "輿論戰",
    "法律戰",
    "科技戰",
    "資訊戰",
    "網路戰",
    "標準戰",
    "專利戰",
    "封鎖消息",
    "新聞封鎖",
    "網路封鎖",
    "封鎖帳號",
    "封鎖言論",
)
_WAR_METAPHOR_EN = re.compile(
    r"\b(?:tariff|trade|price|currency|chip|tech)\s+wars?\b",
    re.I,
)


def _war_scan_key(title: str) -> str:
    """Strip economic-war / news-blackout wording before matching WAR_PHRASES."""
    key = normalize_title(title)
    key = _WAR_METAPHOR_EN.sub(" ", key)
    for m in sorted(_WAR_METAPHOR_ZH, key=len, reverse=True):
        # Do not eat 戰爭 inside 貿易戰爭: only drop the metaphor if the next
        # char is not 爭 (戰爭).
        if m.endswith("戰"):
            key = re.sub(re.escape(m) + r"(?!爭)", " ", key)
        else:
            key = key.replace(m, " ")
    return key


def has_war_event(titles: list[str] | None) -> tuple[bool, str]:
    """True if any title has a war-class phrase (not a high tariff score)."""
    from size_risk import WAR_PHRASES

    for t in titles or []:
        key = _war_scan_key(t)
        for phrase in WAR_PHRASES:
            if phrase_in_title(key, phrase):
                return True, t
    return False, ""


def _mentions_name(title: str, name: str, ticker: str) -> bool:
    key = normalize_title(title)
    n = normalize_title(name or "")
    if n and n in key:
        return True
    code = (ticker or "").split(".")[0].lower()
    return bool(code) and code in key


def has_name_lock(titles: list[str] | None, name: str, ticker: str) -> tuple[bool, str]:
    from size_risk import NAME_LOCK_PHRASES

    for t in titles or []:
        if not _mentions_name(t, name, ticker):
            continue
        key = normalize_title(t)
        for phrase in NAME_LOCK_PHRASES:
            if phrase_in_title(key, phrase):
                return True, t
    return False, ""


def _save_name_news(payload: dict) -> None:
    folder = PAPER / "name_news"
    folder.mkdir(parents=True, exist_ok=True)
    ticker = str(payload.get("ticker") or "x").replace(".", "_").replace("^", "")
    session = str(payload.get("session") or "na")
    path = folder / f"{session}_{ticker}.json"
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def name_heat(ticker: str, name: str, session=None) -> dict:
    """Live RSS for one name. Used at 16:00 when a breakout is queued."""
    session = pd.Timestamp(session or datetime.now(TAIPEI).date()).normalize()
    dstr = session.strftime("%Y-%m-%d")
    queries: list[str] = []
    if name:
        queries.extend([str(name), f"{name} 利空", f"{name} 關稅"])
    code = (ticker or "").split(".")[0]
    if code:
        queries.append(f"{code} Taiwan")
    titles: list[str] = []
    ok = 0
    for q in queries:
        got = _fetch_rss(q)
        if got:
            ok += 1
        titles.extend(got)
    scored = score_titles(titles)
    fetched = ok > 0
    heat = int(scored.get("news_score") or 0)
    trend = preview_trend(heat, fetched)
    if not fetched:
        trend = "unknown"
    war, war_t = has_war_event(scored.get("unique_titles") or titles)
    nlock, nlock_t = has_name_lock(scored.get("unique_titles") or titles, name, ticker)
    out = {
        "session": dstr,
        "ticker": ticker,
        "name": name,
        "updated_at": _now_iso(),
        "news_fetched": fetched,
        "fetch_ok": ok,
        "fetch_total": len(queries),
        "news_score": heat,
        "trend": trend,
        "war_lock": war,
        "name_lock": nlock,
        "lock": bool(war or nlock),
        "lock_title": war_t or nlock_t,
        "n_unique": scored.get("n_unique", 0),
        "n_raw": scored.get("n_raw", 0),
        "off_headlines": scored.get("off_headlines") or [],
        "on_headlines": scored.get("on_headlines") or [],
    }
    _save_name_news(out)
    return out


def _fetch_rss(query: str, n: int = 8) -> list[str]:
    q = urllib.parse.quote(query)
    url = (
        "https://news.google.com/rss/search?q="
        + q
        + "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    titles: list[str] = []
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        for item in root.iter("item"):
            title = item.findtext("title") or ""
            title = re.sub(r"\s+", " ", title).strip()
            if title:
                titles.append(title)
            if len(titles) >= n:
                break
    except Exception:
        return []
    return titles


def twii_stress(twii: pd.DataFrame | None, session: pd.Timestamp) -> dict:
    out = {"d1": None, "d3": None, "price_pause": False}
    if twii is None or twii.empty or "Close" not in twii.columns:
        return out
    d = pd.Timestamp(session).normalize()
    c = twii["Close"].astype(float)
    c = c[c.index <= d]
    if len(c) < 4:
        return out
    last = float(c.iloc[-1])
    prev = float(c.iloc[-2])
    prev3 = float(c.iloc[-4])
    d1 = last / prev - 1.0 if prev else 0.0
    d3 = last / prev3 - 1.0 if prev3 else 0.0
    out["d1"] = round(d1, 4)
    out["d3"] = round(d3, 4)
    out["price_pause"] = bool(d1 <= D1_PAUSE or d3 <= D3_PAUSE)
    return out


def load_risk(path: Path | None = None) -> dict | None:
    path = path or RISK_PATH
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_risk(result: dict, path: Path | None = None) -> Path:
    path = path or RISK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _live_book() -> dict:
    """Cash / equity / names from live paper account (best-effort)."""
    out = {"cash": "", "equity": "", "n_positions": "", "holdings": ""}
    acct_path = PAPER / "account.json"
    raw = load_risk(acct_path)
    if not raw:
        return out
    pos = raw.get("positions") or []
    names = []
    for p in pos:
        if int(p.get("shares") or 0) > 0:
            names.append(str(p.get("name") or p.get("ticker") or ""))
    out["cash"] = raw.get("cash", "")
    out["equity"] = raw.get("equity", "")
    out["n_positions"] = len(names)
    out["holdings"] = "／".join(names)
    return out


def preview_trend(heat: int | None, fetched: bool) -> str:
    if not fetched:
        return "unknown"
    if heat is None:
        return ""
    if heat >= SEVERE:
        return "severe"
    if heat >= HOT:
        return "hot"
    return "cool"


def _journal_has(session: str, slot: str) -> bool:
    if not JOURNAL_PATH.exists() or JOURNAL_PATH.stat().st_size == 0:
        return False
    import csv

    try:
        with JOURNAL_PATH.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if str(row.get("session") or "") == session and str(row.get("slot") or "") == slot:
                    return True
    except OSError:
        return False
    return False


def append_journal(result: dict, extra: dict | None = None) -> Path:
    """Append one daily row. Does not flatten live positions.

    would_flat=1 means: if we later turn on 消息面停損, this print would
    have queued exits. We only record it for now.
    Skips if this session+slot is already in the file (watcher + 排程雙跑).
    """
    extra = extra or {}
    session = str(result.get("session") or "")
    slot = str(result.get("slot") or "")
    if session and slot and _journal_has(session, slot):
        return JOURNAL_PATH
    book = _live_book()
    book.update({k: v for k, v in extra.items() if v is not None and v != ""})
    slot = str(result.get("slot") or "")
    fetched = bool(result.get("news_fetched", True))
    heat = result.get("news_score")
    heat_i = None if heat is None or heat == "" else int(heat)
    trend = str(result.get("trend") or "")
    if not trend:
        trend = preview_trend(heat_i, fetched)
    price_pause = bool(result.get("price_pause"))
    news_allow = result.get("news_allow")
    if news_allow is None and slot == "2130":
        news_allow = trend in ("cool", "cooling")
    would_flat = int(
        trend in ("hot", "severe", "unknown") or price_pause
    )
    row = {
        "logged_at": result.get("updated_at") or _now_iso(),
        "session": result.get("session") or "",
        "slot": slot,
        "algo": result.get("algo") or "heat_v1",
        "heat": "" if heat_i is None else heat_i,
        "n_unique": result.get("n_unique", ""),
        "n_raw": result.get("n_raw", ""),
        "fetch_ok": result.get("fetch_ok", ""),
        "fetch_total": result.get("fetch_total", ""),
        "trend": trend,
        "news_allow": "" if news_allow is None else int(bool(news_allow)),
        "allow_new_entries": (
            "" if result.get("allow_new_entries") is None
            else int(bool(result.get("allow_new_entries")))
        ),
        "would_flat": would_flat,
        "prev_score": result.get("prev_score", ""),
        "prev_session": result.get("prev_session", ""),
        "twii_d1": result.get("twii_d1", ""),
        "twii_d3": result.get("twii_d3", ""),
        "price_pause": int(price_pause),
        "cash": book.get("cash", ""),
        "equity": book.get("equity", ""),
        "n_positions": book.get("n_positions", ""),
        "holdings": book.get("holdings", ""),
        "reason": str(result.get("reason") or result.get("note") or ""),
    }
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    new_file = (not JOURNAL_PATH.exists()) or JOURNAL_PATH.stat().st_size == 0
    with JOURNAL_PATH.open("a", encoding="utf-8-sig", newline="") as f:
        import csv

        w = csv.DictWriter(f, fieldnames=JOURNAL_COLS)
        if new_file:
            w.writeheader()
        w.writerow({c: row.get(c, "") for c in JOURNAL_COLS})
    return JOURNAL_PATH


def _fetch_scored(session: pd.Timestamp, slot: str) -> dict:
    titles: list[str] = []
    ok = 0
    for q in QUERIES:
        got = _fetch_rss(q)
        if got:
            ok += 1
        titles.extend(got)
    scored = score_titles(titles)
    return {
        "session": pd.Timestamp(session).strftime("%Y-%m-%d"),
        "slot": slot,
        "updated_at": _now_iso(),
        "news_fetched": ok > 0,
        "fetch_ok": ok,
        "fetch_total": len(QUERIES),
        "algo": "heat_v1",
        **scored,
    }


def decide_news(curr_heat: int, prev_heat: int | None) -> tuple[bool, str, str]:
    """Return (pause, trend, reason).

    trend: cool | cooling | hot | severe
    """
    if prev_heat is None:
        if curr_heat >= HOT:
            return True, "hot", f"今08:30熱度 {curr_heat} ≥ {HOT}(尚無昨21:30)"
        return False, "cool", f"今08:30熱度 {curr_heat} < {HOT}(尚無昨21:30,先看這一筆)"

    delta = curr_heat - prev_heat
    if curr_heat >= SEVERE:
        return (
            True,
            "severe",
            f"今早熱度 {curr_heat} ≥ 嚴重線 {SEVERE}(昨21:30={prev_heat},Δ{delta:+d})減到最低檔",
        )
    if curr_heat < HOT:
        return (
            False,
            "cool",
            f"今早已涼 {curr_heat} < {HOT}(昨21:30={prev_heat},Δ{delta:+d})",
        )
    if prev_heat - curr_heat >= COOLING_DROP:
        return (
            False,
            "cooling",
            f"仍偏熱 {curr_heat} 但隔夜降溫 {prev_heat}→{curr_heat}(降≥{COOLING_DROP})允許開倉",
        )
    return (
        True,
        "hot",
        f"仍熱且未明顯降溫:昨21:30={prev_heat} 今08:30={curr_heat}(Δ{delta:+d})",
    )


def snapshot_2130(session: pd.Timestamp | str | None = None) -> dict:
    """Weekday 21:30 heat only. Tomorrow 08:30 will compare against this."""
    session = pd.Timestamp(session or datetime.now(TAIPEI).date()).normalize()
    snap = _fetch_scored(session, "2130")
    snap["note"] = "21:30 熱度,隔日 08:30 比升降溫;本日開關仍看今早結論"
    save_risk(snap, SNAPSHOT_2130_PATH)
    append_journal(snap)
    try:
        (PAPER / "last_news_2130.txt").write_text(
            datetime.now(TAIPEI).strftime("%Y-%m-%d %H:%M:%S"),
            encoding="utf-8",
        )
    except OSError:
        pass
    return snap


def morning_0830(
    session: pd.Timestamp | str | None = None,
    twii: pd.DataFrame | None = None,
) -> dict:
    """Weekday 08:30: fetch now, compare heat trend with last 21:30."""
    session = pd.Timestamp(session or datetime.now(TAIPEI).date()).normalize()
    curr = _fetch_scored(session, "0830")
    prev = load_risk(SNAPSHOT_2130_PATH)
    if prev is None:
        prev = load_risk(PAPER / "news_snapshot_0930.json")
    px = twii_stress(twii, session)
    prev_heat = None if prev is None or prev.get("news_score") is None else int(prev["news_score"])

    if not curr.get("news_fetched", False):
        # RSS fetch failed entirely: 0/5 queries returned anything, so
        # news_score is 0 not because the news is calm but because we have
        # no signal at all. Fail-safe: pause, don't treat silence as "cool".
        news_pause, trend = True, "unknown"
        news_reason = (
            f"新聞抓取全部失敗({curr.get('fetch_ok', 0)}/{curr.get('fetch_total', len(QUERIES))} "
            "成功),視為無訊號,暫停開新倉"
        )
    else:
        news_pause, trend, news_reason = decide_news(int(curr["news_score"]), prev_heat)

    from size_risk import macro_size_weight

    war_lock, war_title = has_war_event(curr.get("unique_titles") or curr.get("off_headlines"))
    unknown = trend == "unknown" or not curr.get("news_fetched", False)
    lock_new = bool(unknown or war_lock or px["price_pause"])
    size_weight = macro_size_weight(trend, lock_new)
    old_switch = bool(news_pause or px["price_pause"])

    reasons = [news_reason]
    if war_lock:
        reasons.append(f"戰爭級硬關:{war_title[:40]}")
    if px["price_pause"]:
        reasons.append(f"大盤壓力 d1={px['d1']} d3={px['d3']}")
    if not lock_new:
        reasons.append(f"新倉檔位 {size_weight:.0%}")
    news_allow = not news_pause
    result = {
        **curr,
        "compared": True,
        "trend": trend,
        "news_allow": news_allow,
        "lock_new": lock_new,
        "war_lock": war_lock,
        "war_title": war_title,
        "size_weight": size_weight,
        "old_switch_would_block": old_switch,
        "allow_new_entries": (not lock_new),
        "prev_session": None if prev is None else prev.get("session"),
        "prev_slot": None if prev is None else prev.get("slot"),
        "prev_score": prev_heat,
        "twii_d1": px["d1"],
        "twii_d3": px["d3"],
        "price_pause": px["price_pause"],
        "reason": "；".join(reasons),
        "prev_off_headlines": [] if prev is None else (prev.get("off_headlines") or [])[:4],
    }
    save_risk(result, RISK_PATH)
    append_journal(result)
    stamp = PAPER / "last_news_0830.txt"
    try:
        stamp.write_text(
            datetime.now(TAIPEI).strftime("%Y-%m-%d %H:%M:%S"),
            encoding="utf-8",
        )
    except OSError:
        pass
    return result


def attach_twii(decision: dict, twii: pd.DataFrame | None, session: pd.Timestamp) -> dict:
    """Reuse the 08:30 decision; only refresh TWII stress at the close."""
    from size_risk import macro_size_weight

    out = dict(decision)
    px = twii_stress(twii, session)
    news_allow = bool(out.get("news_allow", True))
    scanned_war, war_t = has_war_event(out.get("unique_titles") or out.get("off_headlines"))
    war_lock = scanned_war
    out["war_title"] = war_t
    out["war_lock"] = war_lock
    unknown = str(out.get("trend") or "") == "unknown" or not out.get("news_fetched", True)
    lock_new = bool(war_lock or unknown or px["price_pause"])
    out["twii_d1"] = px["d1"]
    out["twii_d3"] = px["d3"]
    out["price_pause"] = px["price_pause"]
    out["lock_new"] = lock_new
    out["size_weight"] = macro_size_weight(str(out.get("trend") or "cool"), lock_new)
    out["allow_new_entries"] = not lock_new
    out["old_switch_would_block"] = bool((not news_allow) or px["price_pause"])
    reason = str(out.get("reason") or "")
    price_bit = f"大盤壓力 d1={px['d1']} d3={px['d3']}"
    if px["price_pause"] and price_bit not in reason:
        out["reason"] = (reason + "；" + price_bit).strip("；")
    out["updated_at"] = _now_iso()
    return out


def evaluate_risk(
    session: pd.Timestamp | str,
    twii: pd.DataFrame | None = None,
    fetch_news: bool = True,
) -> dict:
    session = pd.Timestamp(session).normalize()
    dstr = session.strftime("%Y-%m-%d")
    if fetch_news:
        saved = load_risk(RISK_PATH)
        if (
            saved
            and saved.get("compared")
            and saved.get("slot") == "0830"
            and str(saved.get("session") or "") == dstr
        ):
            return attach_twii(saved, twii, session)
        return morning_0830(session, twii=twii)

    px = twii_stress(twii, session)
    lock_new = bool(px["price_pause"])
    allow = not lock_new
    reasons = []
    if px["price_pause"]:
        reasons.append(f"大盤壓力 d1={px['d1']} d3={px['d3']}")
    if not reasons:
        reasons.append("回放無新聞標題:滿額檔位 20%")
    return {
        "session": dstr,
        "updated_at": _now_iso(),
        "allow_new_entries": allow,
        "lock_new": lock_new,
        "war_lock": False,
        "size_weight": 0.0 if lock_new else 0.20,
        "old_switch_would_block": lock_new,
        "news_fetched": False,
        "news_score": 0,
        "trend": "cool",
        "twii_d1": px["d1"],
        "twii_d3": px["d3"],
        "price_pause": px["price_pause"],
        "reason": "；".join(reasons),
        "off_headlines": [],
        "on_headlines": [],
    }


if __name__ == "__main__":
    import argparse

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="TW paper news heat (not a broker)")
    ap.add_argument("--slot", choices=("0830", "2130"), default="0830")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        # same story, two publishers → one title
        s = score_titles(
            [
                "川普對台加徵關稅 - 經濟日報",
                "川普對台加徵關稅 - Yahoo股市",
                "台海爆發軍事衝突導彈封鎖 - 範例",
                "Fed降息鴿派市場樂觀 - 範例",
            ]
        )
        assert s["n_unique"] == 3, s
        # two copies of tariff should not double
        assert s["news_score"] < 20, s

        # longer phrase must win over the shorter phrase it contains —
        # these would previously double-count (e.g. -2 + 1 = -1 instead of -2)
        h, off, on = headline_heat("央行宣布取消關稅")
        assert h == -2 and off == [] and on == ["取消關稅"], (h, off, on)

        h, off, on = headline_heat("政府宣布全面性關稅措施")
        assert h == 2 and off == ["全面性關稅"] and on == [], (h, off, on)

        ok_w, _ = has_war_event(["台海爆發軍事衝突導彈封鎖 - 範例"])
        assert ok_w
        ok_t, _ = has_war_event(["川普對台加徵關稅 - 經濟日報"])
        assert not ok_t
        steel = "【即時新聞】川普掀美加關稅戰！紐柯鋼鐵(NUE)等這4檔鋼鐵股狂飆，透視供應鏈洗牌下的真正贏家！"
        ok_steel, _ = has_war_event([steel])
        assert not ok_steel, "關稅戰 must not hard-lock"
        mash = "【全球大頭條】中東衝突再起？美國爭奪石油控制權中國防台海衝突遭能源斷供｜西藏土石流死亡數與尼泊爾差太多外媒記者控北京封鎖消息｜#鏡新聞"
        ok_mash, _ = has_war_event([mash])
        assert not ok_mash, "封鎖消息 must not hard-lock"
        ok_real, _ = has_war_event(["外媒：解放軍演練封鎖台灣港口 - 範例"])
        assert ok_real
        ok_tw, _ = has_war_event(["Trump tariff war lifts US steel stocks"])
        assert not ok_tw

        h, off, on = headline_heat("Fed signals pause tariff plan")
        assert h == -2 and on == ["pause tariff"], (h, off, on)

        # a plain generic mention still scores on its own
        h, off, on = headline_heat("政府研議調高關稅")
        assert h == 1 and off == ["關稅"], (h, off, on)

        # English whole-word: warning ≠ war; tariffs still counts as tariff
        h, off, on = headline_heat("Fed warning on inflation")
        assert h == 0 and off == [] and on == [], (h, off, on)
        h, off, on = headline_heat("risk of war in the strait")
        assert h == 3 and off == ["war"], (h, off, on)
        h, off, on = headline_heat("US considers new tariffs")
        assert h == 1 and off == ["tariff"], (h, off, on)
        h, off, on = headline_heat("a big deal for exporters")
        assert h == 0, (h, off, on)

        pause, trend, _ = decide_news(8, 12)
        assert pause is False and trend == "cooling", (pause, trend)
        pause, trend, _ = decide_news(4, 10)
        assert pause is False and trend == "cool", (pause, trend)
        pause, trend, _ = decide_news(13, 16)
        assert pause is True and trend == "severe", (pause, trend)
        pause, trend, _ = decide_news(5, None)
        assert pause is False and trend == "cool", (pause, trend)

        h, off, on = headline_heat(
            "川普稱美加協議「幾乎談妥」 汽車關稅可望由25%降至15%"
        )
        assert h < 0 and "關稅" not in off, (h, off, on)
        h, off, on = headline_heat("川普又TACO 加拿大50%關稅生效前踩剎車")
        assert h < 0 and "關稅" not in off, (h, off, on)
        h, off, on = headline_heat(
            "台積電分析美國關稅及出口管制帶來挑戰 一文看有哪些多重風險"
        )
        assert h == 0, (h, off, on)
        h, off, on = headline_heat(
            "川普關稅違憲！他酸「台積電白送了」：買了天價保險無法退費"
        )
        assert h <= 0 and "關稅" not in off, (h, off, on)
        scored = score_titles(
            [
                "川普稱美加協議「幾乎談妥」 汽車關稅可望由25%降至15% - Yahoo股市",
                "川普又TACO 加拿大50%關稅生效前踩剎車-新聞內容-基金 - MoneyDJ",
            ]
        )
        assert scored["off_headlines"] == [], scored
        assert scored["news_score"] < 0, scored

        print("self-test ok", s)
    elif args.slot == "2130":
        print(json.dumps(snapshot_2130(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(morning_0830(), ensure_ascii=False, indent=2))
