# 持股熱力圖 v1

## 公式
- **今日漲跌** = 同筆有效報價的 `last / prev_close - 1`。非當日報價顯示「—」。
- **買入後損益** = 帳戶持股 `last / avg - 1`（不另估費用）。

## 占比分母
占「該帳戶有效正市值合計」（不含現金）。無效／非正市值列入「無法配置面積」清單並明示。

## 面積（AC-3）
使用 squarified treemap + absolute positioning。各有效方塊的 DOM 像素面積占比與市值占比絕對差 ≤ 1 百分點。
驗證：
```bash
python snr_backtest/test_holdings_heatmap_v1.py
python snr_backtest/test_heatmap_area_dom.py
```

## 安裝與離線驗證
```bash
pip install -r requirements-heatmap.txt
playwright install chromium
python snr_backtest/test_holdings_heatmap_v1.py
python snr_backtest/test_heatmap_area_dom.py
python snr_backtest/scripts/take_heatmap_evidence.py
```
截圖輸出至 `web/heatmap_evidence/`（可選擇是否納入 repo）。完全離線，不連網、不讀真實 paper／quotes。

## 時點與過期
持倉快照時點與報價時點分開標示。模擬過期門檻：盤中 300s、盤後 3600s（台北時間）。

## Fixture 場景與截圖證據（AC-11）
腳本 `scripts/take_heatmap_evidence.py` 產出：

| 檔名 | 說明 |
|------|------|
| `paper_day_heat.png` | 紙上帳戶 · 今日漲跌熱力圖 |
| `paper_pnl_heat.png` | 紙上帳戶 · 買入後損益熱力圖 |
| `paper_table.png` | 紙上帳戶 · 原表格視圖（含代號、股數、市值、今日漲跌、買入後損益） |
| `sim_normal_day_heat.png` | 模擬帳戶 · 正常（非過期）今日漲跌熱力圖 |
| `sim_normal_pnl_heat.png` | 模擬帳戶 · 正常（非過期）買入後損益熱力圖 |
| `paper_missing.png` | 紙上熱力圖 + 「無法配置面積」清單（列出無效／非正市值） |
| `paper_empty.png` | 紙上熱力圖空態「沒有持股」 |
| `paper_invalid_cost.png` | 紙上熱力圖 · 買入後損益模式（無效成本顯示「—」） |
| `sim_stale.png` | 過期快照 + 舊持股 |
| `load_fail.png` | 載入失敗文案 |

輔助函式（fixture 內）：`setColorMode(prefix, 'day'|'pnl')`、`setViewMode(prefix, 'heat'|'table')`。  
表格模式會依 `window._paperData`／`_simData` 填入 `#pos`／`#simpos`。  
腳本在需要熱力圖證據的場景會主動切回 heat 模式。
