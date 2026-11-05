# giga_quant：佳必琪（6197）NN 選股與量化擇時（規格 v4）

**正式口徑：real（nn_tf_real.py + backtest_real.py）**  
舊版 `nn_tf.py` / `backtest_portfolio.py` 標為 **legacy**，僅供對照。所有數字都是實際跑出來的。

## 資料與方法（real 口徑）
- **資料**：TEJ 月資料。路徑由環境變數 `PANEL_PATH` 決定，預設 `trade_NN/data/panel.pkl`（相對於檔案所在資料夾，非 cwd）。gitignore 排除。
- **y**：下月含息報酬，每月上下 2.5% 縮尾，再減掉樣本市值加權的市場報酬。
- **X**：14 個價量特徵，每月先在 1%/99% 縮尾，再做 z-score，缺值補 0。
  - mom_1, mom_6, mom_12, mom_36, chmom_6
  - retvol, maxret, beta
  - mvel1, dolvol, turn, stdturn, stddolvol, ill
- **切分**：
  - 訓練：2001/09–2009/02
  - 驗證：2009/03–2014/02
  - 測試（樣本外）：2014/03–2026/08
  - 每 12 個月重訓一次，訓練期逐年加長（expanding），驗證期固定 60 個月往前滾。
- **TF-NN3**：
  - 架構：32-16-8，每層 Dense → BatchNorm → ReLU。
  - 正則化：L1，強度在 {1e-5, 1e-4, 1e-3} 中依驗證 MSE 選。
  - 訓練：Adam，學習率 1e-3，batch 2048；early stopping patience 5，回到最好的權重。
  - Ensemble：5 個 seed 平均。
- **real 口徑差異**：
  - 測試月份包含 `ret_next` 缺值股票（下市／停牌），計數 > 0。
  - 下市持股預設 −100%（保守），無 `fillna(0)` 路徑；停牌為 0。
  - 成交：t 月底出訊號 → t+1 月第一個交易日開盤成交，持有到 t+2 月第一個交易日開盤。
  - 產業：使用 `data/industry.csv`（來自 TWSE ISIN 和 TPEx OpenAPI 的現行分類，欄位 code,name,market,industry），不加日期維度。最新月份 panel 查不到產業的一律歸「未知」並受 15% 上限。
  - **回測使用現行產業分類，非當時分類。**
  - 產業上限：未知 15%（n=20 時最多 3 檔），其他 30%（最多 6 檔）。
  - 名次口徑：Top20 = 新買入門檻（前 20 名）；緩衝 40 = 續抱門檻（仍在前 40 名可續抱）。目標檔有「篩選後名次」欄。  
    **AC-6 字面實作**：續抱 filtered_rank >= 40、新買 filtered_rank >= 20 時發出警示（規格寫「小於」）。若實務上應包含第 20／第 40 名，可再調整。
  - yfinance 僅暫補，標「暫定」，可重算；正式來源 TEJ。
  - 覆蓋率 < 85%：非 0 結束碼、印通知（out/alerts.log + 可選 ALERT_WEBHOOK_URL）、不寫 `paper_target`。
- **成本**：買進手續費 0.1425%（每筆最低 NT$20）；賣出 0.1425% 手續費 + 0.3% 證交稅；滑價 0.1%。

## 執行順序（本機，out/ 不上傳 git）

    python nn_tf_real.py
    python backtest_real.py
    python watchlist.py --live
    python paper_trade.py
    python monitor.py

## 檔案說明
- `nn_tf_real.py` / `backtest_real.py`：正式 real 口徑
- `nn_tf.py` / `backtest_portfolio.py`：**legacy**
- `fetch_oct2026_yf_v2.py`：已修正 AC-8，yfinance 暫補標「暫定」
- `portfolio.py`：未知 15% / 其他 30%
- `risk.py`：讀取現行 industry.csv，查不到歸「未知」
- `paper_trade.py`：覆蓋率檢查、篩選後名次、完整上期結算
- `snr_backtest/nn_paper.py`：費用改走 `broker.py`（最低 NT$20）
- `check_ac4.py` / `check_ac13.py`：驗收測試

## 使用者決定（2026-11-05）
公開 repo `kendottv/trade` 僅收程式與 README。  
`trade_NN/data/`、`out/`、`paper/` 以 `.gitignore` 排除，本機同步即可。AC-11／AC-12 相關驗證為本機驗證／gitignore 例外。

## 限制
- **樣本小**：只看一檔股票或有限投組，約 150 個月，雜訊很大。
- **事後挑選**：「最佳模型」是看完結果才挑的，所以結果偏樂觀。
- **市場報酬**：用樣本市值加權平均代理，不是 TEJ 報酬指數。
- **特徵**：論文 36 個特徵這裡只有 12 個，沒有基本面；另外加了 2 個（mom_36、beta）。
- **成本**：有扣手續費和證交稅與滑價，但未考慮流動性與容量限制。
- **NN 的隨機性**：NN 有隨機性，換 seed 或 TensorFlow 版本，數字會小幅變動。
- **期間偏差**：6197 在測試期整體表現強，結果帶有期間偏差。
- **下市處理**：正式口徑下市 −100%，legacy 路徑曾以 0 計，已標為 legacy。
- **產業**：回測使用現行產業分類，非當時分類；查不到歸「未知」（上限 15%）。
- **覆蓋率**：最新月份有效資料 < 85% 時不產生目標檔。
- **名次口徑**：AC-6 目前依字面「小於」實作（>= 警示），實務上前 20／前 40 通常含第 20、40 名，可再確認。
