"""紙上交易（只模擬，不下任何真實委託；不碰 trade-coach 或任何真實 trades.db）。
規格 v4：
- AC-2：上期結算缺值／下市預設 −100%，正式績效路徑無 fillna(0)
- AC-6：filtered_rank 為流動性篩選後、產業上限前的同一套名次；加續抱／新買欄；檢查續抱≤40、新買≤20；產業上限遞補標註備註
- AC-9：覆蓋率 <85% 或 panel 讀取失敗 → 非 0 結束、寫 out/alerts.log 通知（可選環境變數 ALERT_WEBHOOK_URL）、不寫 paper_target
- 產業：現行 industry.csv，查不到歸「未知」並受 15% 上限
流程：python watchlist.py --live → 產生 out/live_preds_all.csv
      python paper_trade.py [--nav 1000000]
"""
import argparse, sqlite3, sys, os, numpy as np, pandas as pd
from datetime import datetime
from portfolio import liquidity_screen, select, weights
from risk import industry_map
from costs import BUY, SELL

DB = "paper/paper_ledger.db"
ALERT_LOG = "out/alerts.log"

def notify(msg: str):
    """AC-9 通知：寫入 out/alerts.log，並可選 POST 到環境變數 ALERT_WEBHOOK_URL（不讀任何金鑰檔）。"""
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

ap = argparse.ArgumentParser()
ap.add_argument("--nav", type=float, default=1_000_000)
ap.add_argument("--db", default=DB)
a = ap.parse_args()
DB = a.db

# 讀取最新預測
try:
    L = pd.read_csv("out/live_preds_all.csv", dtype={"code": str})
except FileNotFoundError:
    notify("錯誤：找不到 out/live_preds_all.csv，請先跑 watchlist.py --live")
    sys.exit(1)
mon = L["mon"].iloc[0]
L = L.rename(columns={"pred_excess_ret": "score"})

# 讀取 panel 計算覆蓋率（AC-9）；讀不到視為失敗
try:
    P = pd.read_pickle("data/panel.pkl")
    P["ym"] = P["mon"].dt.strftime("%Y-%m")
    expected = P[P.ym == mon]["code"].nunique()
    valid = L.merge(P[P.ym == mon][["code", "close", "dv", "mcap"]], on="code", how="inner")
    valid = valid.dropna(subset=["close", "dv", "mcap"])
    coverage = len(valid) / max(expected, 1)
except Exception as e:
    notify(f"錯誤：無法讀取 data/panel.pkl 計算覆蓋率（{e}），視為失敗，不產生目標檔")
    sys.exit(1)

if coverage < 0.85:
    notify(f"⚠ 覆蓋率 {coverage:.1%} < 85%（有效 {len(valid)} / 應有 {expected}），本月不產生目標檔。請檢查資料來源。")
    sys.exit(1)

# 合併 panel 資料
try:
    L = L.merge(P[P.ym == mon][["code", "name", "dv", "mcap", "close", "beta"]], on="code", how="left")
except Exception:
    notify("警告：無法合併 panel 資料，部分欄位可能缺失")

# 名稱
try:
    _N = pd.read_csv("data/stock_names.csv", dtype={"code": str}, encoding="utf-8-sig").set_index("code")["name"]
    L["name"] = [f"{c} {_N[c]}" if c in _N.index else f"{c} (名稱待查)" for c in L["code"]]
except FileNotFoundError:
    print("警告：找不到 data/stock_names.csv，沿用原名稱")
    if "name" not in L.columns:
        L["name"] = L["code"]

con = sqlite3.connect(DB)
con.executescript("""
create table if not exists portfolios(
    mon text, code text, name text, industry text, score real, rank int,
    filtered_rank int, hold_type text, weight real, price real, shares int, note text
);
create table if not exists orders(mon text, code text, name text, side text, shares int, price real, est_cost real, note text);
create table if not exists marks(mon text primary key, held_month text, port_ret real, mkt_ret real, nav_before real, nav_after real, status text);
""")

# ---- 1) mark-to-market 前期（AC-2：缺值／下市預設 −100%，無 fillna(0)）----
prev_mon = pd.read_sql("select max(mon) m from portfolios where mon<?", con, params=(mon,))["m"].iloc[0]
nav = a.nav
prev = pd.DataFrame()
if prev_mon:
    prev = pd.read_sql("select * from portfolios where mon=?", con, params=(prev_mon,))
    nav0 = pd.read_sql("select nav_after from marks order by mon desc limit 1", con)
    nav = float(nav0.nav_after.iloc[0]) if len(nav0) else a.nav
    nxt = (pd.Period(prev_mon, "M") + 1).strftime("%Y-%m")
    try:
        R = P[P.ym == nxt].set_index("code")
        if len(R):
            r = R["ret"].reindex(prev.code)
            r = r.fillna(-1.0)  # 下市／缺值預設 −100%
            pr = float((prev.weight.values * r).sum())
            B = P[P.ym == prev_mon].drop(columns="ret", errors="ignore").merge(R[["ret"]], left_on="code", right_index=True).dropna(subset=["mcap", "ret"])
            mr = float(np.average(B.ret, weights=B.mcap)) if len(B) else 0.0
            con.execute("insert or replace into marks values(?,?,?,?,?,?,?)",
                        (prev_mon, nxt, pr, mr, nav, nav * (1 + pr), "marked"))
            nav *= 1 + pr
            print(f"前期 {prev_mon} 投組（持有 {nxt}）: 紙上報酬 {pr:.2%}，市場 {mr:.2%}，NAV {nav:,.0f}")
        else:
            print(f"前期 {prev_mon} 投組：{nxt} 報酬尚未進資料，暫不結算")
    except Exception as e:
        print(f"前期結算失敗（{e}），沿用原 NAV")

# ---- 2) 目標投組（AC-6）----
u = liquidity_screen(L.dropna(subset=["dv", "mcap", "close"]))
ind = industry_map()
prev_codes = list(prev.code) if len(prev) else []
codes, rank_map, notes = select(u, 20, prev=prev_codes, buffer=40, ind=ind, ind_cap=0.30, ind_cap_unknown=0.15)
w = weights(u, codes, "ew")

T = u.set_index("code").loc[codes, ["name", "score", "close"]].reset_index()
T["industry"] = T.code.map(ind).fillna("未知")
T["filtered_rank"] = T.code.map(rank_map)
T["hold_type"] = ["續抱" if c in prev_codes else "新買" for c in T.code]
T["note"] = T.code.map(notes).fillna("")
T["weight"] = w.values
T["shares"] = np.floor(nav * T.weight / T.close).astype(int)
T["mon"] = mon
T["rank"] = T["filtered_rank"]  # 相容舊欄位

# 檢查（AC-6）
keep_mask = T.hold_type == "續抱"
new_mask = T.hold_type == "新買"
if (T.loc[keep_mask, "filtered_rank"] > 40).any():
    notify("警告：有續抱股 filtered_rank > 40")
if (T.loc[new_mask, "filtered_rank"] > 20).any() and not T.loc[new_mask & (T.filtered_rank > 20), "note"].eq("產業上限遞補").all():
    notify("警告：有新買股 filtered_rank > 20 且未標註產業上限遞補")

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

T.to_csv(f"out/paper_target_{mon}.csv", index=False, encoding="utf-8-sig")
O.to_csv(f"out/paper_orders_{mon}.csv", index=False, encoding="utf-8-sig")
print(f"訊號月 {mon}（持有 {(pd.Period(mon, 'M') + 1).strftime('%Y-%m')}），覆蓋率 {coverage:.1%}，NAV {nav:,.0f}，{len(T)} 檔，{len(O)} 筆模擬委託")
print(T[["code", "name", "industry", "filtered_rank", "hold_type", "score", "weight", "close", "shares", "note"]].to_string(index=False))
