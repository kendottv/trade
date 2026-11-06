# 持股熱力圖 v1

## 公式
- **今日漲跌** = 同筆有效報價的 `last / prev_close - 1`。非當日報價顯示「—」。
- **買入後損益** = 帳戶持股 `last / avg - 1`（不另估費用）。

## 占比分母
占「該帳戶有效正市值合計」（不含現金）。無效／非正市值列入「無法配置面積」清單並明示。

## 面積（AC-3）
使用 squarified treemap + absolute positioning。各有效方塊的 DOM 像素面積占比與市值占比絕對差 ≤ 1 百分點。

## 原表格欄位（AC-2）
切回表格時僅切換 visibility，不覆寫 `#pos`／`#simpos`。  
紙上原 8 欄：股票／股數／權重／成本／現價／損益／報酬／NN名次。  
模擬原 7 欄：股票／股數／成本／現價／損益／報酬／備註（含 legacy「舊持股、待清倉」）。

## 報價總時限（Risks）
整批 enrichment 硬上限 ≤9 秒（明顯小於前端 15s Abort）。  
`as_completed` 逾時會被捕捉，未完成檔位寫入 cache=`None`，後續不再同步長等。

## 時點與過期
持倉快照時點與報價時點分開標示。模擬過期門檻：盤中 300s、盤後 3600s（台北時間）。

## 規格 AC 原文（節錄）
AC-1 兩帳戶各自顯示所有持股，包含模擬帳戶舊持股及其原有標示；不得混合帳戶資料。  
AC-2 兩邊皆能切換熱力圖／原表格，原表格欄位保留；預設熱力圖及今日漲跌模式。  
AC-3 有效市值方塊依市值比例配置面積，扣除標題、間距後面積占比與市值占比差距不超過 1 個百分點。…  
AC-5 今日漲跌＝同筆有效報價的現價除以昨收再減一；買入後損益＝帳戶持股現價除以平均成本再減一。  
AC-6 缺報價、昨收無效、成本無效 → 顯示「—」，不冒充 0%。  
AC-8 非當日報價不得冒稱今日漲跌；過期快照須標示。  
（完整規格見對話紀錄或 repo 內 `spec_v1_verbatim.md`）

## 安裝與離線驗證
```bash
pip install -r requirements-heatmap.txt
playwright install chromium
python snr_backtest/test_holdings_heatmap_v1.py
python snr_backtest/test_heatmap_area_dom.py
python snr_backtest/test_webapp_heatmap_enrich.py
python snr_backtest/scripts/take_heatmap_evidence.py
```

## 預期執行 log 樣式
```text
$ python snr_backtest/test_holdings_heatmap_v1.py
ALL PASS

$ python snr_backtest/test_heatmap_area_dom.py
AREA CHECK PASS max_dev=0.0000

$ python snr_backtest/test_webapp_heatmap_enrich.py
ALL ENRICH TESTS PASS
```

## Fixture 場景與截圖證據（AC-11）
腳本 `scripts/take_heatmap_evidence.py` 產出：

| 檔名 | 說明 |
|------|------|
| `paper_day_heat.png` | 紙上帳戶 · 今日漲跌熱力圖 |
| `paper_pnl_heat.png` | 紙上帳戶 · 買入後損益熱力圖 |
| `paper_table.png` | 紙上帳戶 · 原表格視圖（8 欄） |
| `sim_normal_day_heat.png` | 模擬帳戶 · 正常（非過期）今日漲跌熱力圖 |
| `sim_normal_pnl_heat.png` | 模擬帳戶 · 正常（非過期）買入後損益熱力圖 |
| `sim_table.png` | 模擬帳戶 · 原表格視圖（7 欄，含備註） |
| `paper_missing.png` | 紙上熱力圖 + 「無法配置面積」清單 |
| `paper_empty.png` | 紙上熱力圖空態「沒有持股」 |
| `paper_invalid_cost.png` | 紙上熱力圖 · 買入後損益模式（無效成本顯示「—」） |
| `sim_stale.png` | 過期快照 + 舊持股 |
| `load_fail.png` | 載入失敗文案 |
