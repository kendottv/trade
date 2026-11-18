# strategy_combo 研究回測（v5）

本目錄為獨立研究回測模組。不修改每日系統、不連任何外部交易介面、不讀取金鑰或帳戶檔。

## 如何執行

在 repo 根目錄執行：

```bash
python -m unittest discover research/strategy_combo/tests
python research/strategy_combo/run.py
```

成功後會在 `research/strategy_combo/out/` 產生 `report.md` 以及相關 CSV／PNG。

## 假設本金

新台幣 1,000,000。

## 資料來源與路徑

- NN3 正式基準（只讀）`Desktop\trade_NN\out\portfolio_monthly.csv`  
  主策略欄位：`Top20 等權 緩衝40 產業≤30%`
- 加權指數：`snr_backtest/data/TWII.csv`
- 時點股票池（會 commit）：`inputs/tw50_membership_intervals.csv`  
  來源與補正說明見 `inputs/README.md`。
- yfinance（87 檔 + 0050 + 00632R）：`period="max"`, `auto_adjust=True`，快取於 `data/`（不 commit）。已有 CSV 時略過重新下載。
- TEJ（僅 6 檔：2311、2325、3474、3697、2823、2888）：  
  必須將「調整股價(日)-除權息調整」匯出檔放在  
  `research/strategy_combo/inputs/tej/tej_prices_a.txt`（來自 Kendo 桌面 `TEJ20261117104345`）  
  `research/strategy_combo/inputs/tej/tej_prices_b.txt`（來自 Kendo 桌面 `TEJ20261117104518`）  
  這些檔案已被 `.gitignore` 排除，**不可 commit**。  
  缺任一檔時 `run.py` 會在開始抓資料前以非 0 結束，並印出完整說明（含兩個檔案的完整路徑），不產生 `report.md`。  
  程式不會改抓 yfinance、不會略過這 6 檔、不會退回使用目前成分股。

## 費率

- 手續費：0.1425%，最低 20 元
- 滑價：每邊 0.1%
- 賣出證交稅：個股 0.3%；ETF（0050、00632R）0.1%  
  **此 ETF 稅率與系統 config.py 的 0.3% 不同**。
- NN3 月報酬已含成本，不重算。

## 共同期間

起點：NN3 有月報酬、加權指數 200 日均線已可計算、0050 與 00632R 皆有日價的第一個完整月份。  
終點：NN3 最後一個月（2026-08）。  
不再看 B 成分股價格起點，也不要求可交易股票 ≥ 10 檔。  
若完整月份數 < 36，報告開頭會標明樣本不足。

## 其他重要聲明

- 風險縮放係數使用共同期間全期資料計算，存在前視偏誤。係數 > 1 時未計入融資或借券成本。
- B 使用時點正確的成分股區間，2311 與 3711 視為不同股票。
- 剔除與價格中斷在最後一個有效收盤強制賣出（當日報酬仍計入）。
- 200 日均線與 B 的進場／出場參數皆固定，未做最佳化。
- `data/`、`out/`、`inputs/tej/` 不進 repo。

## 安全界限

- 不連任何券商或下單介面。
- 不讀寫交易資料庫、紙上帳戶目錄或帳戶設定檔。
- 不讀取環境變數檔或金鑰檔。
- 不修改排程批次檔或儀表板程式。

## 測試

```bash
python -m unittest discover research/strategy_combo/tests
```

必須全部通過、0 skip。
