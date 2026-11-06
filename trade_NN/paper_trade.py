"""紙上交易（只模擬，不下任何真實委託；不碰 trade-coach 或任何真實 trades.db）。
規格 v5：
- 正式訊號月預測來源：out/preds_tf_real.pkl 的 TF-NN3 欄（nn_tf_real.py 產生）。
  live_preds_all.csv 只提供訊號月份，不可用其獨立模型分數覆蓋正式分數。
- AC-2：上期結算缺值／下市預設 −100%，正式績效路徑無 fillna(0)
- AC-6 / AC-7：filtered_rank 為流動性篩選後、產業上限前的同一套名次；續抱 ≤40、新買 ≤20（含邊界）；產業上限遞補標註備註
- AC-9：覆蓋率 <85% 或 panel 讀取失敗 → 非 0 結束、寫 out/alerts.log 通知（可選環境變數 ALERT_WEBHOOK_URL）、不寫 paper_target
- AC-12（v5）：以 live_preds_all.csv 的月份為訊號月，該月必須存在於 preds_tf_real.pkl。
  檢查在寫入 paper_target 以及任何下單／帳戶更新之前執行。
  月份不一致、檔案缺少、月份欄位讀不到或格式不對 → 非 0 結束、不寫入也不改動目標檔、發一則通知。
- 資料路徑由環境變數 PANEL_PATH 決定，預設 trade_NN/data/panel.pkl（相對於本檔所在資料夾）
- 產業：現行 industry.csv，「未知」為產業桶、上限 15%
流程：python watchlist.py --live → 產生 out/live_preds_all.csv（分數來自正式來源）
      python paper_trade.py [--nav 1000000]
"""
import argparse, sqlite3, sys, os, numpy as np, pandas as pd
from datetime import datetime
from portfolio import liquidity_screen, select, weights
from risk import industry_map
from costs import BUY, SELL

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PANEL = os.path.join(HERE, "data", "panel.pkl")
PANEL_PATH = os.environ.get("PANEL_PATH", DEFAULT_PANEL)
DB_DEFAULT = "paper/paper_ledger.db"
ALERT_LOG = "out/alerts.log"

def notify(msg: str):
    """AC-9 / AC-12 通知：寫入 out/alerts.log，並可選 POST 到環境變數 ALERT_WEBHOOK_URL（不讀任何金鑰檔）。"""
    os.makedirs("out", exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    with open(ALERT_LOG, "a", encoding="utf-8") as f:
        f.write(line)
    print(msg)
    webhook = os.environ.get("ALERT_WEBHOOK_URL")
    if webhook:
        try:
            import urllib.request
            req = urllib.request.Request(webhook, data=msg.encode("utf-8"), method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

def migrate_portfolios(con):
    cur = con.execute("PRAGMA table_info(portfolios)")
    cols = {row[1] for row in cur.fetchall()}
    if "filtered_rank" not in cols:
        con.execute("ALTER TABLE portfolios ADD COLUMN filtered_rank int")
    if "hold_type" not in cols:
        con.execute("ALTER TABLE portfolios ADD COLUMN hold_type text")
    if "note" not in cols:
        con.execute("ALTER TABLE portfolios ADD COLUMN note text")
    con.commit()

def check_signal_month(live_path="out/live_preds_all.csv", real_path="out/preds_tf_real.pkl"):
    """AC-12（v5）：以 live 月份為訊號月，必須存在於 preds_tf_real.pkl。
    回傳 (mon, ok, msg)。任何失敗都應非 0 結束且不寫目標檔。"""
    if not os.path.exists(live_path):
        return None, False, f"AC-12 失敗：缺少 {live_path}"
    if not os.path.exists(real_path):
        return None, False, f"AC-12 失敗：缺少 {real_path}"
    try:
        L = pd.read_csv(live_path, dtype={"code": str})
        if "mon" not in L.columns or L["mon"].isna().all():
            return None, False, "AC-12 失敗：live_preds_all.csv 月份欄位讀不到或格式不對"
        mon = str(L["mon"].iloc[0]).strip()
        if len(mon) < 7 or mon[4] != "-":
            return None, False, f"AC-12 失敗：訊號月格式不對：{mon}"
    except Exception as e:
        return None, False, f"AC-12 失敗：讀取 live_preds_all.csv 錯誤：{e}"
    try:
        R = pd.read_pickle(real_path)
        if "mon" not in R.columns:
            return None, False, "AC-12 失敗：preds_tf_real.pkl 缺少 mon 欄"
        real_mons = set(R["mon"].astype(str).str[:7].unique())
        if mon not in real_mons and mon[:7] not in real_mons:
            return mon, False, f"AC-12 失敗：訊號月 {mon} 不存在於 preds_tf_real.pkl"
    except Exception as e:
        return None, False, f"AC-12 失敗：讀取 preds_tf_real.pkl 錯誤：{e}"
    return mon, True, "OK"

def load_formal_scores(mon, real_path="out/preds_tf_real.pkl"):
    """載入正式訊號月的 TF-NN3 分數（v5 正式來源）。"""
    R = pd.read_pickle(real_path)
    R["ym"] = R["mon"].astype(str).str[:7]
    sub = R[R["ym"] == mon][["code", "TF-NN3"]].copy()
    if len(sub) == 0:
        raise ValueError(f"正式來源無訊號月 {mon} 的分數")
    return sub.rename(columns={"TF-NN3": "score"})

def _load_industry(industry_path=None):
    """生產預設呼叫 industry_map()；測試可傳入路徑。"""
    if industry_path is None:
        return industry_map()
    df = pd.read_csv(industry_path, dtype={"code": str}, encoding="utf-8-sig")
    return dict(zip(df["code"], df["industry"].fillna("未知")))

def _load_names(names_path=None):
    """生產預設讀 data/stock_names.csv；測試可傳入路徑。"""
    path = names_path or os.path.join(HERE, "data", "stock_names.csv")
    try:
        return pd.read_csv(path, dtype={"code": str}, encoding="utf-8-sig").set_index("code")["name"]
    except FileNotFoundError:
        return pd.Series(dtype=str)

def main(live_path=None, real_path=None, panel_path=None, out_dir=None, db_path=None,
         industry_path=None, names_path=None, notifier=None, nav=1_000_000):
    """Production 主流程。測試可傳入路徑與 notifier；正常 CLI 不傳則使用預設。"""
    live_path = live_path or "out/live_preds_all.csv"
    real_path = real_path or "out/preds_tf_real.pkl"
    panel_path = panel_path or PANEL_PATH
    out_dir = out_dir or "out"
    db_path = db_path or DB_DEFAULT
    _notify = notifier or notify

    # AC-12 檢查（在任何寫入、下單、帳戶更新之前）
    mon, ok, msg = check_signal_month(live_path, real_path)
    if not ok:
        _notify(msg)
        return 1

    try:
        L = pd.read_csv(live_path, dtype={"code": str})
    except FileNotFoundError:
        _notify("錯誤：找不到 live_preds_all.csv")
        return 1

    # 正式分數覆蓋：只用 preds_tf_real.pkl 的 TF-NN3，不用 live 的 pred_excess_ret
    try:
        formal = load_formal_scores(mon, real_path)
        L = L.drop(columns=["pred_excess_ret", "score"], errors="ignore").merge(formal, on="code", how="inner")
    except Exception as e:
        _notify(f"錯誤：無法載入正式分數（{e}）")
        return 1

    # 讀取 panel 計算覆蓋率（AC-9）
    try:
        P = pd.read_pickle(panel_path)
        P["ym"] = P["mon"].dt.strftime("%Y-%m")
        expected = P[P.ym == mon]["code"].nunique()
        valid = L.merge(P[P.ym == mon][["code", "close", "dv", "mcap"]], on="code", how="inner")
        valid = valid.dropna(subset=["close", "dv", "mcap"])
        coverage = len(valid) / max(expected, 1)
        print(f"覆蓋率：{coverage:.1%}（有效 {len(valid)} / 應有 {expected}）")
    except Exception as e:
        _notify(f"錯誤：無法讀取 panel（{panel_path}）（{e}），視為失敗，不產生目標檔")
        return 1

    if coverage < 0.85:
        _notify(f"⚠ 覆蓋率 {coverage:.1%} < 85%（有效 {len(valid)} / 應有 {expected}），本月不產生目標檔。請檢查資料來源。")
        return 1

    try:
        L = L.merge(P[P.ym == mon][["code", "name", "dv", "mcap", "close", "beta"]], on="code", how="left")
    except Exception:
        _notify("警告：無法合併 panel 資料，部分欄位可能缺失")

    # 名稱（可注入）
    _N = _load_names(names_path)
    if len(_N):
        L["name"] = [f"{c} {_N[c]}" if c in _N.index else f"{c} (名稱待查)" for c in L["code"]]
    elif "name" not in L.columns:
        L["name"] = L["code"]

    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript("""
    create table if not exists portfolios(
        mon text, code text, name text, industry text, score real, rank int,
        filtered_rank int, hold_type text, weight real, price real, shares int, note text
    );
    create table if not exists orders(mon text, code text, name text, side text, shares int, price real, est_cost real, note text);
    create table if not exists marks(mon text primary key, held_month text, port_ret real, mkt_ret real, nav_before real, nav_after real, status text);
    """)
    migrate_portfolios(con)

    # ---- 1) mark-to-market 前期（AC-2：缺值／下市預設 −100%）----
    prev_mon = pd.read_sql("select max(mon) m from portfolios where mon<?", con, params=(mon,))["m"].iloc[0]
    nav_val = nav
    prev = pd.DataFrame()
    if prev_mon:
        prev = pd.read_sql("select * from portfolios where mon=?", con, params=(prev_mon,))
        nav0 = pd.read_sql("select nav_after from marks order by mon desc limit 1", con)
        nav_val = float(nav0.nav_after.iloc[0]) if len(nav0) else nav
        nxt = (pd.Period(prev_mon, "M") + 1).strftime("%Y-%m")
        try:
            R = P[P.ym == nxt].set_index("code")
            if len(R):
                r = R["ret"].reindex(prev.code)
                r = r.fillna(-1.0)
                pr = float((prev.weight.values * r).sum())
                B = P[P.ym == prev_mon].drop(columns="ret", errors="ignore").merge(R[["ret"]], left_on="code", right_index=True).dropna(subset=["mcap", "ret"])
                mr = float(np.average(B.ret, weights=B.mcap)) if len(B) else 0.0
                con.execute("insert or replace into marks values(?,?,?,?,?,?,?)",
                            (prev_mon, nxt, pr, mr, nav_val, nav_val * (1 + pr), "marked"))
                nav_val *= 1 + pr
                print(f"前期 {prev_mon} 投組（持有 {nxt}）: 紙上報酬 {pr:.2%}，市場 {mr:.2%}，NAV {nav_val:,.0f}")
            else:
                print(f"前期 {prev_mon} 投組：{nxt} 報酬尚未進資料，暫不結算")
        except Exception as e:
            print(f"前期結算失敗（{e}），沿用原 NAV")

    # ---- 2) 目標投組（AC-6 / AC-7）----
    u = liquidity_screen(L.dropna(subset=["dv", "mcap", "close"]))
    ind = _load_industry(industry_path)
    prev_codes = list(prev.code) if len(prev) else []
    codes, rank_map, notes = select(u, 20, prev=prev_codes, buffer=40, ind=ind, ind_cap=0.30, ind_cap_unknown=0.15)
    w = weights(u, codes, "ew")

    T = u.set_index("code").loc[codes, ["name", "score", "close"]].reset_index()
    T["industry"] = T.code.map(ind).fillna("未知")
    T["filtered_rank"] = T.code.map(rank_map)
    T["hold_type"] = ["續抱" if c in prev_codes else "新買" for c in T.code]
    T["note"] = T.code.map(notes).fillna("")
    T["weight"] = w.values
    T["shares"] = np.floor(nav_val * T.weight / T.close).astype(int)
    T["mon"] = mon
    T["rank"] = T["filtered_rank"]

    # 檢查（邊界含第 20 / 第 40 名）
    keep_mask = T.hold_type == "續抱"
    new_mask = T.hold_type == "新買"
    if (T.loc[keep_mask, "filtered_rank"] > 40).any():
        _notify("警告：有續抱股 filtered_rank > 40")
    if (T.loc[new_mask, "filtered_rank"] > 20).any():
        bad = T.loc[new_mask & (T.filtered_rank > 20)]
        if not (bad["note"] == "產業上限遞補").all():
            _notify("警告：有新買股 filtered_rank > 20 且未標註產業上限遞補")

    con.execute("delete from portfolios where mon=?", (mon,))
    con.execute("delete from orders where mon=?", (mon,))
    T.rename(columns={"close": "price"})[["mon", "code", "name", "industry", "score", "rank", "filtered_rank", "hold_type", "weight", "price", "shares", "note"]].to_sql("portfolios", con, if_exists="append", index=False)

    # ---- 3) 模擬委託單 ----
    old = dict(zip(prev.code, prev.shares)) if len(prev) else {}
    new = dict(zip(T.code, T.shares))
    px = L.set_index("code")["close"]
    nm = L.set_index("code")["name"]
    O = []
    for c in sorted(set(old) | set(new)):
        d = new.get(c, 0) - old.get(c, 0)
        if d == 0:
            continue
        p = float(px.get(c, np.nan))
        side = "BUY" if d > 0 else "SELL"
        O.append((mon, c, nm.get(c, ""), side, abs(int(d)), p, abs(d) * p * (BUY if d > 0 else SELL), "SIMULATED ONLY"))
    O = pd.DataFrame(O, columns=["mon", "code", "name", "side", "shares", "price", "est_cost", "note"])
    O.to_sql("orders", con, if_exists="append", index=False)
    con.commit()

    # 寫入目標檔（AC-12 已通過）
    os.makedirs(out_dir, exist_ok=True)
    target_path = os.path.join(out_dir, f"paper_target_{mon}.csv")
    orders_path = os.path.join(out_dir, f"paper_orders_{mon}.csv")
    T.to_csv(target_path, index=False, encoding="utf-8-sig")
    O.to_csv(orders_path, index=False, encoding="utf-8-sig")
    print(f"訊號月 {mon}（持有 {(pd.Period(mon, 'M') + 1).strftime('%Y-%m')}），覆蓋率 {coverage:.1%}，NAV {nav_val:,.0f}，{len(T)} 檔，{len(O)} 筆模擬委託")
    print(T[["code", "name", "industry", "filtered_rank", "hold_type", "score", "weight", "close", "shares", "note"]].to_string(index=False))
    return 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--nav", type=float, default=1_000_000)
    ap.add_argument("--db", default=DB_DEFAULT)
    a = ap.parse_args()
    sys.exit(main(db_path=a.db, nav=a.nav))
