# 台股 NN 選股 · 紙上帳戶

以神經網路（NN3）做台股橫斷面選股，搭配紙上帳戶與看盤面板。作品集專案，主題為佳必琪（6197）。

> **只做模擬，不會下真單。** 不構成任何投資建議。

最後更新：2026-10-30

---

## 1. 概要

- **模型**：NN3 橫斷面模型，預測每檔股票**下個月的超額報酬**（相對大盤），不是預測股價。重點在**排名**，不是數值本身。
- **範圍**：只涵蓋上市櫃普通股，不含興櫃、ETF。
- 模型訓練與每月預測在另一個專案 `trade_NN`（不在本 repo）。本 repo 只讀它的輸出（`trade_NN\out`，可用環境變數 `NN_OUT_DIR` 覆寫），不在這台重新訓練。

## 2. 策略

**主策略（組合）**
- NN 分數前 20 名、等權。
- 緩衝區 40：已持有的股票掉出前 20 但仍在前 40 就續抱，降低週轉。
- 單一產業上限 30%。
- 流動性篩選：當月市值、成交值任一落在全市場後 20% 就排除。
- 每月調倉。

**6197 擇時**
- 6197 預測值 > 0 時持有 6197，否則持有大盤。
- 測過加 20 日／60 日均線的大盤濾網，結果都變差，所以不加。

## 3. 回測結果

成本：買進手續費 0.1425%；賣出手續費 0.1425% + 證交稅 0.3%；另計滑價 0.1%。

| 策略 | CAGR | Sharpe | 最大回撤 |
| --- | --- | --- | --- |
| Top20 等權・緩衝 40・產業上限 30%（主策略） | 31.5% | 1.26 | −30.0% |
| Top20 等權・緩衝 40 | 29.0% | 1.20 | −30.0% |
| Top20 等權・無緩衝 | 26.9% | 1.14 | −29.1% |
| 多空 D10−D1（beta 中性） | 7.0% | 0.58 | −32.4% |
| 市場（樣本市值加權） | 18.3% | 1.07 | −25.6% |

- IC 平均 0.057（t = 7.34）。
- 多空效果弱，模型價值主要在做多端的排名。
- 模型無法預判整體大盤下跌：它預測的是相對大盤的超額報酬。

資料來源：`trade_NN\out\portfolio_metrics.csv`。

## 4. NN 紙上帳戶

- 2026-10-29 開帳，起始資金 NT$1,000,000，依主策略的當月目標持股建倉。
- 帳戶檔在 `snr_backtest\paper_nn\`：`account.json`、`ledger.csv`、`equity.csv`、`daily_log.md`。
- 每天 16:00 由 `nn_paper.py --daily` 用收盤價更新權益。
- 行情只用模擬／公開資料，程式中沒有下單功能。

## 5. 看盤面板

`webapp.py`（FastAPI），用 `start_dashboard.bat` 啟動，網址 http://127.0.0.1:8501 。深色主題。

- 頂部行情條：加權指數、台指期（平日 08:45–13:45 顯示日盤，其他時間顯示夜盤）。
- 權益曲線與目前持股（代號後附公司名稱）。
- 自選股（含 6197）的 NN 排名。
- 全市場前 20 名。
- 模型監控（IC 等）。
- 新聞（只顯示，不影響交易）。
- 右下角可拖曳的機器人聊天泡泡，點開是 trade-coach 投資教練的聊天視窗。trade-coach 是另一個專案（不在本 repo），`start_dashboard.bat` 會一併啟動。

## 6. 資料夾結構

```
snr_backtest\
  nn_strategy.py       讀 trade_NN\out 的目標持股與策略參數
  nn_paper.py          NN 紙上帳戶（--daily 每日更新）
  webapp.py, web\      面板後端與前端
  quotes.py            行情來源（永豐模擬報價，沒金鑰時用公開資料）
  stock_names.py       代號 → 公司名稱
  build_stock_names.py 建立公司名稱表
  coach_bridge.py      把新聞摘要交給 trade-coach（只顯示）
  broker.py            交易成本試算（不是券商）
  paper_nn\            NN 紙上帳戶檔
  legacy\              舊的 SNR 突破策略、新聞風控、舊面板（已停用，保留參考）
  git_daily.bat        每日自動 commit + push
```

## 7. 安裝與執行（Windows）

```bat
cd snr_backtest
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
start_dashboard.bat
```

Windows 排程（只在主機 Kendo 上跑；其他電腦只看不推）：

| 時間 | 工作 |
| --- | --- |
| 16:00 | `nn_paper.py --daily` 更新紙上帳戶 |
| 08:30、21:30 | `coach_bridge` 新聞摘要 |
| 21:55 | `git_daily` 自動推到 GitHub |

## 8. 金鑰

- 複製 `snr_backtest\paper\broker_secrets.example.json` 為 `broker_secrets.json`，自己填入永豐 API 金鑰。
- trade-coach 那邊複製 `.env.example` 為 `.env` 自己填。
- 這些檔案已列入 `.gitignore`，**絕對不要 commit**。沒填金鑰時改用公開資料。

## 9. 免責聲明

本專案僅供學習與作品展示，回測結果不代表未來績效，不構成任何投資建議。所有交易皆為紙上模擬。