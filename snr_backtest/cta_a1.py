r"""CTA A1 訊號：加權指數收盤 vs 200 日均線。

執行時先把 TWII 日 K 補到含當日（quotes.get_feed 或 Yahoo / data.get_price end_date=None），
再算 200 日簡單均線，覆寫 paper_nn/a1_signal.json，並在 a1_signals.csv 追加或覆蓋同日一列。
資料不足 200 交易日、或當日收盤拿不到時：為當天寫 stale=true（訊號沿用前一筆 on/off），
不覆蓋前一筆非 stale 紀錄，結束碼 0，stdout 印原因。不新增任何 Shioaji 登入點。
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import data  # noqa: E402
import quotes  # noqa: E402
import tw_calendar  # noqa: E402

TZ = timezone(timedelta(hours=8))
PAPER = Path(os.getenv("PAPER_NN_DIR", ROOT / "paper_nn"))
SIGNAL_JSON = PAPER / "a1_signal.json"
SIGNALS_CSV = PAPER / "a1_signals.csv"
CSV_COLS = ["date", "close", "ma200", "signal", "source", "stale"]


def now_iso() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def _load_prev() -> dict | None:
    if not SIGNAL_JSON.exists():
        return None
    try:
        return json.loads(SIGNAL_JSON.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_signal(rec: dict, overwrite_date: str | None = None) -> None:
    """Write JSON (latest) and CSV. For stale, append/overwrite only today's date; keep prior non-stale rows."""
    PAPER.mkdir(parents=True, exist_ok=True)
    # JSON is always the latest record (may be today's stale)
    SIGNAL_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = []
    if SIGNALS_CSV.exists():
        with SIGNALS_CSV.open(encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r.get("date") != rec["date"]]
    # only write known columns (ignore reason)
    clean = {c: rec.get(c, "") for c in CSV_COLS}
    rows.append(clean)
    with SIGNALS_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def update() -> int:
    """Return 0 always (stale is not an error)."""
    today = now_iso()
    prev = _load_prev()
    reason = None
    close = None
    ma200 = None
    source = "unknown"
    df = None
    try:
        df = data.get_price("^TWII", end_date=None)
        if df is None or df.empty:
            # AC-1: still try quotes feed when data fails
            feed = quotes.get_feed()
            bar = feed.session_bar(quotes.INDEX_YAHOO) or feed.session_bar(quotes.INDEX_SHIOAJI)
            if bar and bar.get("Close"):
                # build minimal df with today's bar and save
                import pandas as pd
                df = pd.DataFrame(
                    [{"Open": bar.get("Open", bar["Close"]), "High": bar.get("High", bar["Close"]),
                      "Low": bar.get("Low", bar["Close"]), "Close": bar["Close"], "Volume": 0}],
                    index=pd.DatetimeIndex([pd.Timestamp(today)])
                )
                data.save_cache("^TWII", df)
                source = getattr(feed, "name", "quotes")
                close = float(bar["Close"])
            else:
                reason = "無法取得加權指數收盤（data 與 quotes 皆失敗）"
        else:
            source = "data/yahoo"
            last_day = str(df.index[-1])[:10]
            if last_day < today:
                # try overlay today's bar and write back to cache (AC-1)
                feed = quotes.get_feed()
                bar = feed.session_bar(quotes.INDEX_YAHOO)
                if bar and bar.get("Close"):
                    df = quotes.apply_session_bar(df, bar, day=today)
                    data.save_cache("^TWII", df)
                    source = f"{source}+{getattr(feed, 'name', 'quotes')}"
                    close = float(df["Close"].iloc[-1])
                else:
                    reason = f"快取最後交易日 {last_day} 早於今日 {today}，且無法取得當日收盤"
            else:
                close = float(df["Close"].iloc[-1])
            if close is not None and len(df) >= 200:
                ma200 = float(df["Close"].rolling(200).mean().iloc[-1])
            elif close is not None:
                reason = f"資料不足 200 個交易日（目前 {len(df)}）"
    except Exception as e:
        reason = f"更新加權指數失敗：{e}"

    if reason or close is None or ma200 is None:
        # stale for TODAY; copy previous signal value; do not overwrite prior non-stale date
        prev_signal = prev.get("signal", "off") if prev else "off"
        rec = {
            "date": today,
            "close": prev.get("close") if prev else None,
            "ma200": prev.get("ma200") if prev else None,
            "signal": prev_signal,
            "source": "stale",
            "stale": True,
        }
        _write_signal(rec)
        print(f"A1 stale: {reason or '無法計算'}")
        return 0

    signal = "on" if close > ma200 else "off"
    rec = {
        "date": today,
        "close": round(close, 4),
        "ma200": round(ma200, 4),
        "signal": signal,
        "source": source,
        "stale": False,
    }
    _write_signal(rec)
    print(f"A1 {today} close={rec['close']} ma200={rec['ma200']} signal={signal} source={source}")
    return 0


if __name__ == "__main__":
    sys.exit(update())
