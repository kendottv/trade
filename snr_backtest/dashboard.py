"""Local Streamlit panel for the Taiwan paper account.

View P&L, news, watchlist, and strategy knobs. Does not trade and is not a
broker. Saves go to paper/ui_settings.json; live/alert/news pick them up on
the next scheduled run.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from config import INDEX_TICKER, INITIAL_CAPITAL, STRATEGY_DEFAULTS
from data import get_price, load_cache
from quotes import (
    INDEX_YAHOO,
    apply_session_bar,
    get_feed,
    in_cash_session,
    now_taipei,
)
from ui_settings import (
    SETTINGS_PATH,
    TICKER_RE,
    effective_news,
    effective_strategy,
    reset_all,
    save_strategy,
    save_watchlist,
)
from universe import BANK_TICKERS, candidate_tickers, default_catalog, display_name

PAPER = ROOT / "paper"
ACCOUNT = PAPER / "account.json"
EQUITY = PAPER / "equity.csv"
LEDGER = PAPER / "ledger.csv"
NEWS = PAPER / "news_risk.json"
NEWS_2130 = PAPER / "news_snapshot_2130.json"
JOURNAL = PAPER / "news_journal.csv"
ALERTS = PAPER / "alerts.csv"
ALERTS_MD = PAPER / "alerts_today.md"


def _json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except OSError:
        return pd.DataFrame()


def _text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def last_close(ticker: str) -> tuple[float | None, str]:
    try:
        df = load_cache(ticker, end_date=None)
    except Exception:
        df = None
    if df is None or df.empty or "Close" not in df.columns:
        return None, ""
    close = df["Close"].dropna()
    if close.empty:
        return None, ""
    return float(close.iloc[-1]), str(pd.Timestamp(close.index.max()).date())


def load_account() -> dict:
    return _json(ACCOUNT)


def twii_frame() -> pd.DataFrame:
    try:
        df = load_cache(INDEX_TICKER, end_date=None)
    except Exception:
        df = None
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out.index = pd.to_datetime(out.index).normalize()
    need = [c for c in ("Open", "High", "Low", "Close") if c in out.columns]
    if len(need) < 4:
        return pd.DataFrame()
    return out[need].dropna()


def twii_candlestick(df: pd.DataFrame, sma_n: int):
    import plotly.graph_objects as go

    plot = df.copy()
    plot["sma"] = plot["Close"].rolling(sma_n, min_periods=sma_n).mean()
    fig = go.Figure(
        data=[
            go.Candlestick(
                x=plot.index,
                open=plot["Open"],
                high=plot["High"],
                low=plot["Low"],
                close=plot["Close"],
                name="加權",
                increasing_line_color="#e53935",
                increasing_fillcolor="#e53935",
                decreasing_line_color="#43a047",
                decreasing_fillcolor="#43a047",
                whiskerwidth=0.8,
            ),
            go.Scatter(
                x=plot.index,
                y=plot["sma"],
                name=f"SMA{sma_n}",
                mode="lines",
                line=dict(color="#f9a825", width=1.6),
            ),
        ]
    )
    fig.update_layout(
        height=460,
        margin=dict(l=8, r=8, t=8, b=8),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        yaxis_title="指數",
        hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.18)", side="right")
    return fig


@st.fragment(run_every=timedelta(seconds=20))
def twii_live_panel(sma_n: int) -> None:
    """09:00–13:30: poll quote feed every 20s. After hours: daily cache only."""
    feed = get_feed()
    live = in_cash_session()
    daily = twii_frame()
    bar = None
    q = None
    intra = pd.DataFrame()
    if live:
        q = feed.last(INDEX_YAHOO)
        bar = feed.session_bar(INDEX_YAHOO)
        intra = feed.intraday(INDEX_YAHOO)
        if bar is not None:
            daily = apply_session_bar(daily, bar, now_taipei().date())
    if daily.empty:
        st.info("沒有加權行情快取（data/TWII.parquet）。等 16:00 收盤單下載後再看。")
        return

    last = float(daily["Close"].iloc[-1])
    prev = float(daily["Close"].iloc[-2]) if len(daily) > 1 else last
    if q is not None and q.last:
        last = float(q.last)
        if q.prev_close:
            prev = float(q.prev_close)
    chg = last - prev
    chg_pct = (chg / prev * 100) if prev else 0.0
    sma_now = daily["Close"].rolling(int(sma_n), min_periods=int(sma_n)).mean().iloc[-1]
    above = pd.notna(sma_now) and last > float(sma_now)
    if q is not None and q.ts is not None:
        stamp = q.ts.strftime("%H:%M:%S")
    else:
        stamp = str(pd.Timestamp(daily.index.max()).date())
    status = "盤中 20 秒更新" if live else "盤後"

    a, b, c = st.columns(3)
    a.metric("加權", f"{last:,.0f}", f"{chg:+,.0f}（{chg_pct:+.2f}%）")
    b.metric("來源", "Yahoo" if feed.name == "yahoo" else str(feed.name))
    c.metric("狀態", status, stamp)
    st.caption(
        f"SMA{int(sma_n)} {'之上（大盤濾網過）' if above else '之下（大盤濾網擋新倉）'}。"
        "成交仍是收盤確認。Yahoo 會延遲；永豐接點在 quotes.ShioajiFeed，現在不登入、不下單。"
    )

    periods = {"1個月": 22, "3個月": 66, "半年": 132, "1年": 252, "全部": 0}
    pick = st.session_state.get("twii_period", "半年")
    n = periods.get(pick, 132)
    view = daily.tail(n) if n else daily
    st.plotly_chart(
        twii_candlestick(view, int(sma_n)),
        width="stretch",
        config={"displayModeBar": False},
    )
    if live and intra is not None and not intra.empty and "Close" in intra.columns:
        st.caption("今日 1 分線（盤中）")
        st.line_chart(intra[["Close"]].rename(columns={"Close": "加權"}), width="stretch")


st.set_page_config(page_title="紙上帳戶面板", layout="wide", page_icon="📊")
st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; }
      div[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }
    </style>
    """,
    unsafe_allow_html=True,
)

acct = load_account()
news = _json(NEWS)
snap = _json(NEWS_2130)
catalog = default_catalog()
watch = candidate_tickers()
held = {
    p.get("ticker"): p
    for p in (acct.get("positions") or [])
    if p.get("ticker") and int(p.get("shares") or 0) > 0
}
strat = effective_strategy(STRATEGY_DEFAULTS)
news_th = effective_news()

equity = float(acct.get("equity") or INITIAL_CAPITAL)
cash = float(acct.get("cash") or 0)
initial = float(acct.get("initial_cash") or INITIAL_CAPITAL)
pnl = equity - initial
pnl_pct = (pnl / initial * 100) if initial else 0.0
allow = bool(news.get("allow_new_entries"))
lock_new = bool(news.get("lock_new", not allow))
size_w = news.get("size_weight")
heat = news.get("news_score")
trend = news.get("trend") or "—"
session = acct.get("last_session") or "—"

st.title("紙上帳戶面板")
st.caption("只監看、可改設定。不成交、不是券商。設定存檔後，下次 16:00 收盤單／09:00 預警才生效。")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("權益", f"{equity:,.0f}", f"{pnl:+,.0f}（{pnl_pct:+.1f}%）")
c2.metric("現金", f"{cash:,.0f}")
c3.metric("持股", f"{len(held)} 檔")
c4.metric("新聞熱度", f"{heat if heat is not None else '—'}", trend)
if lock_new:
    c5.metric("新倉", "硬關", session)
elif size_w is not None:
    c5.metric("新倉檔位", f"{float(size_w):.0%}", session)
else:
    c5.metric("新倉", "開" if allow else "關", session)

tab_over, tab_pnl, tab_news, tab_watch, tab_strat = st.tabs(
    ["總覽", "損益", "新聞", "監看名單", "策略"]
)

with tab_over:
    left, right = st.columns((1.4, 1))
    with left:
        st.subheader("加權指數")
        st.radio(
            "區間",
            ["1個月", "3個月", "半年", "1年", "全部"],
            index=2,
            horizontal=True,
            key="twii_period",
            label_visibility="collapsed",
        )
        twii_live_panel(int(strat.get("TWII_SMA") or 60))
    with right:
        st.subheader("今天預警")
        day = now_taipei().strftime("%Y-%m-%d")
        acsv = _csv(ALERTS)
        today_alerts = pd.DataFrame()
        if not acsv.empty and "time" in acsv.columns:
            today_alerts = acsv[acsv["time"].astype(str).str.startswith(day)]
        if not today_alerts.empty:
            st.caption("尚未收盤確認，不會進場。")
            for _, r in today_alerts.iterrows():
                t = str(r.get("time") or "")
                hhmm = t[11:16] if len(t) >= 16 else t
                try:
                    last = float(r.get("last") or 0)
                    lvl = float(r.get("prior_high_20") or 0)
                except (TypeError, ValueError):
                    continue
                st.markdown(
                    f"- {hhmm} {r.get('name', '')} ({r.get('ticker', '')}) "
                    f"現價 {last:.2f} > {lvl:.2f}"
                )
        else:
            st.caption("今天還沒有破高預警。")
        pending = acct.get("pending") or []
        st.subheader("排隊（隔日開盤）")
        if pending:
            st.dataframe(pd.DataFrame(pending), use_container_width=True, hide_index=True)
        else:
            st.caption("沒有 pending。")

    st.subheader("目前持股")
    rows = []
    asofs = set()
    for p in acct.get("positions") or []:
        ticker = p.get("ticker")
        shares = int(p.get("shares") or 0)
        avg = float(p.get("avg_price") or 0)
        last, asof = last_close(ticker)
        asofs.add(asof)
        last = last if last is not None else avg
        mv = last * shares
        upnl = (last - avg) * shares
        upct = (last / avg - 1.0) * 100 if avg else 0.0
        rows.append(
            {
                "代號": ticker,
                "名稱": p.get("name") or display_name(ticker),
                "股數": shares,
                "成本": round(avg, 2),
                "收盤": round(last, 2),
                "市值": round(mv, 0),
                "未實現": round(upnl, 0),
                "報酬%": round(upct, 1),
                "進場日": p.get("entry_date") or "",
                "trail": "已開" if p.get("trail_armed") else "未開",
            }
        )
    if rows:
        st.caption("收盤價來自本地快取" + (f"（{max(asofs)}）" if any(asofs) else "。"))
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("目前空手。")

    st.subheader("系統狀態")
    s1, s2, s3, s4 = st.columns(4)
    s1.write(f"收盤單：`{_text(PAPER / 'last_live_run.txt') or '—'}`")
    s2.write(f"預警：`{_text(PAPER / 'last_alert_session.txt') or '—'}`")
    s3.write(f"新聞 08:30：`{_text(PAPER / 'last_news_0830.txt') or '—'}`")
    s4.write(f"新聞 21:30：`{_text(PAPER / 'last_news_2130.txt') or '—'}`")
    if news.get("reason"):
        st.info(news["reason"])

with tab_pnl:
    st.subheader("未實現損益")
    if rows:
        total_mv = sum(r["市值"] for r in rows)
        total_upnl = sum(r["未實現"] for r in rows)
        m1, m2, m3 = st.columns(3)
        m1.metric("持股市值", f"{total_mv:,.0f}")
        m2.metric("未實現", f"{total_upnl:+,.0f}")
        m3.metric("含現金權益", f"{equity:,.0f}")
        st.bar_chart(
            pd.DataFrame(rows).set_index("名稱")["未實現"],
            use_container_width=True,
        )
    else:
        st.caption("沒有持股。")

    st.subheader("帳戶權益曲線")
    eq = _csv(EQUITY)
    if eq.empty:
        st.caption("還沒有 equity.csv")
    else:
        eq = eq.copy()
        eq["date"] = pd.to_datetime(eq["date"], errors="coerce")
        eq = eq.dropna(subset=["date"]).set_index("date")
        if "equity" in eq.columns:
            st.line_chart(eq[["equity"]].rename(columns={"equity": "權益"}))

    st.subheader("成交紀錄")
    ledger = _csv(LEDGER)
    if ledger.empty:
        st.caption("還沒有 ledger.csv")
    else:
        if "action" in ledger.columns:
            sells = ledger[ledger["action"].astype(str) == "sell"]
        else:
            sells = pd.DataFrame()
        if not sells.empty and "reason" in sells.columns:
            wins = sells["reason"].astype(str).isin(["tp", "trail"])
            n = len(sells)
            w = int(wins.sum())
            st.caption(f"已平倉 {n} 筆；其中停利／移動停利 {w} 筆。")
        st.dataframe(ledger.tail(30), use_container_width=True, hide_index=True)

with tab_news:
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("今早 08:30（開關看這筆）")
        st.write(
            f"熱度 **{news.get('news_score', '—')}**　"
            f"趨勢 **{news.get('trend', '—')}**　"
            f"新倉 **{'硬關' if lock_new else ('檔位 ' + format(float(size_w), '.0%') if size_w is not None else ('允許' if allow else '暫停'))}**"
        )
        st.caption(news.get("reason") or "")
        st.markdown("**偏空／風險標題**")
        off = news.get("off_headlines") or []
        if off:
            for h in off:
                st.markdown(f"- {h}")
        else:
            st.caption("沒有。")
        st.markdown("**偏多／降溫標題**")
        on = news.get("on_headlines") or []
        if on:
            for h in on:
                st.markdown(f"- {h}")
        else:
            st.caption("沒有。")
    with col_b:
        st.subheader("昨晚 21:30（給明早比）")
        st.write(
            f"熱度 **{snap.get('news_score', '—')}**　"
            f"session **{snap.get('session', '—')}**"
        )
        st.caption(snap.get("note") or "")
        for h in (snap.get("off_headlines") or [])[:12]:
            st.markdown(f"- {h}")

    st.subheader("新聞 journal（只記帳，不實盤平倉）")
    j = _csv(JOURNAL)
    if j.empty:
        st.caption("還沒有 journal。")
    else:
        show_cols = [
            c
            for c in (
                "logged_at", "session", "slot", "heat", "trend",
                "allow_new_entries", "would_flat", "equity", "holdings", "reason",
            )
            if c in j.columns
        ]
        st.dataframe(j[show_cols].tail(40), use_container_width=True, hide_index=True)

with tab_watch:
    st.subheader("監看哪些股票")
    st.caption(
        "打勾＝預警和收盤選股會看。銀行／金控（富邦金、國泰金、中信金、兆豐金）不監測、不開新倉。"
        "帳上舊倉仍跑停利停損。存檔後下次 09:00／16:00 才生效。"
    )
    held_banks = [BANK_TICKERS[t] for t in held if t in BANK_TICKERS]
    if held_banks:
        st.info("帳上仍有舊倉（只作出場、不監測）：" + "、".join(held_banks))
    current = dict(watch)
    table_src = []
    seen = set()
    for t, n in catalog.items():
        table_src.append(
            {
                "監看": t in current,
                "代號": t,
                "名稱": current.get(t, n),
                "持有": t in held,
            }
        )
        seen.add(t)
    for t, n in current.items():
        if t in seen:
            continue
        table_src.append(
            {"監看": True, "代號": t, "名稱": n, "持有": t in held}
        )
    edited = st.data_editor(
        pd.DataFrame(table_src),
        use_container_width=True,
        hide_index=True,
        disabled=["代號", "持有"],
        column_config={
            "監看": st.column_config.CheckboxColumn("監看", default=True),
            "持有": st.column_config.CheckboxColumn("持有", disabled=True),
        },
        key="watch_editor",
    )

    st.markdown("**加一檔**（上市 `.TW`／上櫃 `.TWO`）")
    a, b, c = st.columns((1, 1, 1))
    new_t = a.text_input("代號", placeholder="例如 2303.TW", label_visibility="collapsed")
    new_n = b.text_input("名稱（可空白）", placeholder="名稱可空白", label_visibility="collapsed")
    add_clicked = c.button("加入名單", use_container_width=True)

    if add_clicked:
        t = (new_t or "").strip().upper()
        if not TICKER_RE.match(t):
            st.error("代號要像 2330.TW 或 5314.TWO")
        elif t in BANK_TICKERS:
            st.error("銀行／金控不列入監測。")
        else:
            name = (new_n or "").strip() or catalog.get(t) or t
            extra = {
                str(r["代號"]).strip().upper(): str(r["名稱"]).strip()
                for _, r in edited.iterrows()
                if (r["監看"] or r["持有"]) and str(r["代號"]).strip().upper() not in BANK_TICKERS
            }
            extra[t] = name
            with st.spinner(f"下載 {t} 行情…"):
                try:
                    df = get_price(t, force_download=True, end_date=None)
                except Exception as exc:  # noqa: BLE001
                    df = None
                    st.warning(f"先加進名單，但行情下載失敗：{exc}")
            if df is None or df.empty:
                st.warning(f"{t} 已列入監看，但還沒有有效行情，流動性篩選可能過不了。")
            try:
                save_watchlist(extra)
                st.success(f"已加入 {t} {name}。下次預警／收盤單會看。")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    if st.button("儲存監看名單", type="primary"):
        nxt: dict[str, str] = {}
        blocked = []
        for _, r in edited.iterrows():
            t = str(r["代號"]).strip().upper()
            if t in BANK_TICKERS:
                continue
            if r["監看"] or (r["持有"] and t not in BANK_TICKERS):
                nxt[t] = str(r["名稱"]).strip() or t
            elif t in held:
                blocked.append(t)
                nxt[t] = str(r["名稱"]).strip() or t
        if blocked:
            st.warning("已持股不能移出監看：" + "、".join(blocked))
        try:
            save_watchlist(nxt)
            st.success(f"已存 {len(nxt)} 檔到 `{SETTINGS_PATH.name}`。")
        except ValueError as exc:
            st.error(str(exc))

    if st.button("恢復內建 30 檔"):
        from ui_settings import load_raw, save_raw

        data = load_raw()
        data.pop("watchlist", None)
        save_raw(data)
        st.success("監看名單改回程式內建（不含銀行）。")
        st.rerun()

with tab_strat:
    st.subheader("策略參數")
    st.caption("不要為了「這週沒進場」就放寬 SNR。新聞門檻也建議等 journal 再動。")
    cur = effective_strategy(STRATEGY_DEFAULTS)
    nth = effective_news()

    col1, col2, col3 = st.columns(3)
    snr_min = col1.number_input(
        "SNR 下限（現況 0.40）",
        min_value=0.20,
        max_value=0.80,
        value=float(cur["BREAKOUT_V2_SNR_MIN"]),
        step=0.01,
        format="%.2f",
    )
    lookback = col2.number_input(
        "突破回看天數", min_value=5, max_value=60, value=int(cur["BREAKOUT_LOOKBACK"]), step=1
    )
    twii_sma = col3.number_input(
        "大盤 SMA", min_value=20, max_value=120, value=int(cur["TWII_SMA"]), step=1
    )

    col1, col2, col3 = st.columns(3)
    tp = col1.number_input(
        "停利", min_value=0.05, max_value=0.80, value=float(cur["BREAKOUT_TP"]), step=0.01, format="%.2f"
    )
    sl = col2.number_input(
        "停損", min_value=0.05, max_value=0.50, value=float(cur["BREAKOUT_SL"]), step=0.01, format="%.2f"
    )
    time_stop = col3.number_input(
        "時間停損（連幾日破前低）",
        min_value=1,
        max_value=10,
        value=int(cur["BREAKOUT_TIME_STOP_DAYS"]),
        step=1,
    )

    col1, col2, col3 = st.columns(3)
    trail = col1.checkbox("移動停利", value=bool(cur["BREAKOUT_V2_TRAIL"]))
    trail_arm = col2.number_input(
        "移動停利啟動（漲幅）",
        min_value=0.04,
        max_value=0.40,
        value=float(cur["BREAKOUT_V2_TRAIL_ARM"]),
        step=0.01,
        format="%.2f",
    )
    trail_lb = col3.number_input(
        "移動停利回看低點天數",
        min_value=5,
        max_value=40,
        value=int(cur["BREAKOUT_V2_TRAIL_LOOKBACK"]),
        step=1,
    )

    col1, col2, col3 = st.columns(3)
    twii_f = col1.checkbox("大盤在均線上才開新倉", value=bool(cur["BREAKOUT_V2_TWII_FILTER"]))
    max_w = col2.number_input(
        "單檔權重上限",
        min_value=0.05,
        max_value=0.50,
        value=float(cur["PAPER_MAX_WEIGHT"]),
        step=0.01,
        format="%.2f",
    )
    lot = col3.number_input(
        "紙上零股單位", min_value=1, max_value=1000, value=int(cur["PAPER_LOT_SIZE"]), step=1
    )
    max_pos = st.number_input(
        "最多同時持股檔數", min_value=1, max_value=10, value=int(cur["MAX_POSITIONS"]), step=1
    )

    st.markdown("**新聞開關門檻**（只影響新倉，不砍舊倉）")
    n1, n2, n3 = st.columns(3)
    hot = n1.number_input("HOT（低於此才算涼）", min_value=1, max_value=40, value=int(nth["HOT"]), step=1)
    severe = n2.number_input(
        "SEVERE（高於此即使降溫也關）", min_value=2, max_value=80, value=int(nth["SEVERE"]), step=1
    )
    cooling = n3.number_input(
        "COOLING_DROP（隔夜至少降幾分才算降溫）",
        min_value=1,
        max_value=20,
        value=int(nth["COOLING_DROP"]),
        step=1,
    )

    if snr_min < 0.40:
        st.warning("SNR 低於 0.40 會讓雜訊突破更容易進場。先前已決定先不放寬。")
    if severe < 12:
        st.warning("SEVERE 低於 12 會更容易開新倉。請等 journal 再決定。")

    b1, b2 = st.columns(2)
    if b1.button("儲存策略", type="primary"):
        save_strategy(
            {
                "BREAKOUT_V2_SNR_MIN": snr_min,
                "BREAKOUT_LOOKBACK": int(lookback),
                "BREAKOUT_TP": tp,
                "BREAKOUT_SL": sl,
                "BREAKOUT_TIME_STOP_DAYS": int(time_stop),
                "BREAKOUT_V2_TWII_FILTER": bool(twii_f),
                "BREAKOUT_V2_TRAIL": bool(trail),
                "BREAKOUT_V2_TRAIL_ARM": trail_arm,
                "BREAKOUT_V2_TRAIL_LOOKBACK": int(trail_lb),
                "TWII_SMA": int(twii_sma),
                "PAPER_MAX_WEIGHT": max_w,
                "PAPER_LOT_SIZE": int(lot),
                "MAX_POSITIONS": int(max_pos),
            },
            news={"HOT": int(hot), "SEVERE": int(severe), "COOLING_DROP": int(cooling)},
        )
        st.success("已寫入 paper/ui_settings.json。下次 16:00／09:00／08:30 才會用新值。")
    if b2.button("全部恢復程式預設"):
        reset_all()
        st.success("已刪除面板覆寫，下次排程用程式內建參數與 30 檔名單。")
        st.rerun()

st.divider()
r1, r2 = st.columns((3, 1))
r1.caption(f"帳戶更新：{acct.get('updated_at') or '—'}　設定檔：{SETTINGS_PATH}")
if r2.button("重新整理"):
    st.rerun()
