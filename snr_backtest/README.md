# 台股 SNR 突破 · 紙上帳戶

給 **Grok Build**（或任何接續的助手）用的專案說明。使用者習慣 **繁體中文**。

這不是券商下單。現金／持股／損益只寫在 `snr_backtest\paper\`。  
現行系統全在 `snr_backtest\`。根目錄舊的 `trade.py`、`trade2.py`、各股 `*_trades.csv` **已刪除**。

最後更新：2026-08-14。

---

## 0. 硬限制

- **中期波段（日 K）**。
- 訊號在 **t 收盤**，成交在 **t+1 開盤**。盤中只預警、不成交。

---

## 1. 這專案在做什麼

1. Kaufman **SNR（訊噪比）** 過濾趨勢品質。  
   SNR = `|收盤_t − 收盤_{t-20}| / Σ|每日漲跌|`。n=20。高＝趨勢乾淨。
2. **breakout_v2** 進出（見 `signals.py`）。
3. 約 30 檔流動台股自動選股，最多同時 5 檔。
4. 紙上帳戶每天收盤後跟著行情走，隔日開盤成交。
5. 消息面只當「能不能開新倉」的開關，不拿新聞挑個股。

進場（全部要過）：收盤破前 20 日高 + SNR_20 ≥ 0.40 + 大盤在 SMA60 上 + 新聞交叉比對允許。  
出場：停利 +25%／停損 −20%；連 3 日收在前 20 日低下方；移動停利（先漲 +12% 後武裝，再收破前 15 日低）。  
紙上零股單位 10 股；單檔最多權益 20%，不 all-in。

---

## 2. 每個程式在幹嘛

路徑都在 `snr_backtest\`。日常紙上只靠 watcher／排程叫下面幾支；其餘是回測與研究。

### 每天會跑的（紙上）

| 檔案 | 幹嘛 |
| --- | --- |
| `paper_watcher.py` | **監看主程式**。08:30–22:00 待著，準時叫新聞、預警、收盤單。自己不下單。 |
| `paper_daily.py` | **紙上進出流程**。收盤確認訊號、排隊；隔日開盤價在紙上加減股。`--live` 寫 `paper\`；`--replay` 寫 `paper\replay\`，不碰 live。 |
| `paper_alert.py` | **盤中預警**。現價破前 20 日高就提示音 + Windows 通知。不成交。`--test` 可當場試鈴聲。 |
| `notify_alert.ps1` | **Windows 通知**。給 `paper_alert.py` 叫右下角 toast，自己不跑。 |
| `news_risk.py` | **新聞小演算法**。去重＋權重熱度＋21:30/08:30 升降溫。只當開倉開關，不選股。每天追加 `paper\news_journal.csv`。 |
| `signals.py` | **現行進出規則（breakout_v2）**。紙上與預警都看這支。 |
| `picker.py` | **自動選股**。當天有訊號的，依 SNR、相對大盤強度排序，空槽才補，最多 5 檔。 |
| `universe.py` | **股票池 + 流動性篩選**。約 30 檔名單；均成交金額、股價、歷史長度不夠就剔除。 |
| `paper_account.py` | **紙上帳戶存檔**。讀寫 `account.json`、`ledger.csv`、`equity.csv`、`daily_log.md`。 |
| `broker.py` | **成交試算**。手續費 0.1425%（最低 20 元）、賣出證交稅 0.3%、零股單位。不是券商。 |

### 參數與資料

| 檔案 | 幹嘛 |
| --- | --- |
| `config.py` | 所有參數：SNR 門檻、停利停損、`PAPER_LOT_SIZE`、`PAPER_MAX_WEIGHT`、回測日期、成本。改規則先改這裡。 |
| `data.py` | 從 Yahoo 下載日 K，快取到 `data\`（parquet/csv）。回測會切在 `END_DATE`；紙上不切。 |

### 回測／研究（不影響紙上倉）

| 檔案 | 幹嘛 |
| --- | --- |
| `strategies.py` | 回測策略定義：breakout_v1／v2、pullback（已放棄）。 |
| `engine.py` | 回測引擎：t 收盤訊號、t+1 開盤成交、停利停損。 |
| `metrics.py` | 從成交與權益算勝率、期望值、回撤、CAGR。 |
| `run.py` | 跑十檔約五年回測，產出 `reports\` 圖表與 CSV。 |
| `tune.py` | 網格搜 breakout_v2 參數。用樣本外成績選，不要亂重跑去擬合。 |

### 啟動用的 bat

| 檔案 | 幹嘛 |
| --- | --- |
| `start_paper_watcher.bat` | 平日 08:30：只啟動 watcher。 |
| `run_news_0830.bat` | **每天** 08:30 抓新聞、交叉比對。 |
| `run_news_2130.bat` | **每天** 21:30 記熱度。 |
| `stop_paper_watcher.bat` | 平日 22:00：先 git 備份，再關掉 watcher。 |
| `git_daily.bat` | **每天** 21:55（關掉前）：`git add .`、commit 當天日期、`git push`。沒改動就只 push。 |
| `run_paper_daily.bat` | 手動跑一次 `--live --download`（會 pause）。 |
| `_run_paper_daily_silent.bat` | 平日 16:00 排程用，不要 pause。 |
| `install_autostart.bat` | 安裝平日 08:30／16:00／22:00 排程（已取消開機自啟）。 |
| `uninstall_autostart.bat` | 拆掉上述排程。 |

### 資料夾

| 路徑 | 幹嘛 |
| --- | --- |
| `paper\` | **live 紙上帳戶**（真的在跟的那本）。 |
| `paper\account.json` | 現金、持股、pending、last_session。 |
| `paper\ledger.csv` | 每一筆紙上買賣。 |
| `paper\equity.csv` | 每日權益。 |
| `paper\daily_log.md` | 人看的每日流水。 |
| `paper\news_risk.json` | 今早 08:30 交叉比對結論。 |
| `paper\news_snapshot_2130.json` | 昨晚 21:30 成績，給明早比。 |
| `paper\news_journal.csv` | 每天 08:30／21:30／16:00 熱度與「若當時砍倉」標記（只記錄、不真砍）。 |
| `paper\replay\` | 回放結果，**不會覆蓋 live**。 |
| `data\` | Yahoo 行情快取。 |
| `reports\` | 五年回測產出。 |
| `.venv\` | 本機 Python 3.12。 |
| `requirements.txt` | pandas numpy yfinance matplotlib pyarrow。 |

---

## 3. 一天時序

台股 09:00–13:30。**盤中不會成交。**

| 時間 | 誰跑 | 做什麼 |
| --- | --- | --- |
| **每天** 08:30 | 排程 `TW_News_0830` | 抓新聞、對上一筆 21:30（含週末／假日） |
| 平日 08:30 | 排程 `TW_Paper_Start` | 啟動 watcher（新聞另由每天那支負責） |
| 平日 09:00–13:30 | `paper_alert.py` | 破高預警，不下單 |
| 平日 16:00 | 排程 `TW_Paper_Account` | 收盤確認、排隊隔日單 |
| 下一交易日開盤 | `paper_daily.py` 處理 pending | 開盤價紙上成交 |
| **每天** 21:30 | 排程 `TW_News_2130` | 記熱度（含週末／假日） |
| **每天** 21:55 | 排程 `TW_Git_Daily` | `git add .` / commit 當天日期 / `git push`（關掉前） |
| 平日 22:00 | 排程 `TW_Paper_Stop` | 再 git 一次當備份，然後關掉 watcher |

電腦當時要開著、要登入。進出只平日；**新聞與 git 七天都跑**。關 VS Code 不影響排程。  
16:00 以排程為主、watcher 只補跑；新聞以每天排程為主，journal 同一天同一格不重複寫。國定假日／週末若快取已是最新交易日，live 不再空下載。

---

## 4. 消息面（小演算法 `heat_v1`）

不選股。只回答：今天能不能開新倉？細節在 `news_risk.py`。

1. Google News 抓標題 → **去重**（不同網站同一則只算一次）
2. **權重熱度**：戰爭／封鎖 3、制裁 2、普通關稅 1；豁免／降息會扣。長詞蓋短詞（與詞庫順序無關）。英文用整詞，`warning` 不會被當成 `war`
3. 單則標題最多貢獻 ±4，避免八則「川普關稅」爆分數
4. **每天** 21:30 記熱度；隔天 08:30 再算一次看升降溫（週末／假日也抓，因為假日一樣會有新聞）
   - 今早熱度 **< 6** → 涼，可開
   - 熱度 6～11 但比昨晚 **降 ≥ 3** → 降溫，可開
   - 熱度 ≥ 12，或仍熱且沒降 → 關
5. 再加：TWII 1 日 ≤ −1.5% 或 3 日 ≤ −3%
6. 沒有昨 21:30 就只看今早。週一對上週五晚上
7. Replay 不抓標題，只看大盤跌幅
8. 每天寫入 `paper\news_journal.csv`（熱度、升降溫、會不會開新倉、`would_flat`＝若有消息面停損會不會砍舊倉）。**現在不真的砍倉**，過幾個月用這份再決定。

舊倉照停利／停損／移動停利。

---

## 5. 怎麼跑

在 `snr_backtest`：

```bat
.venv\Scripts\python paper_daily.py --live --download
.venv\Scripts\python paper_alert.py
.venv\Scripts\python paper_alert.py --test
.venv\Scripts\python news_risk.py --slot 0830
.venv\Scripts\python news_risk.py --slot 2130
.venv\Scripts\python paper_daily.py --replay-from 2026-02-14 --replay-to 2026-08-14
.venv\Scripts\python run.py
.venv\Scripts\python tune.py
```

`--live` 改 `paper\`。`--replay` 寫 `paper\replay\`。

---

## 6. 現況快照（2026-08-14 22:00）

- live：富邦金／國泰金／兆豐金，權益約 **2,013,403**，`last_session=2026-08-14`。trail 已武裝。
- 08-14 收盤 0 檔訊號。新聞分數高（關稅）→ 暫停開新倉。
- 21:30 成績 31 已存。週一 08:30 交叉比對。
- 半年 replay（現行零股+20%）：100 萬 → **1,401,263**，14 筆、勝率 71.4%。見 `paper\replay\week_summary.md`。
- **5 年／10 年紙上組合**（同一規則、無標題新聞）：見 `paper\replay_long.md`。5 年 100 萬→**311.9 萬**、勝率 64.7%、CAGR 約 26%、最大回撤 −26%（同期大盤 +172%、MDD −32%）。10 年→**668.5 萬**、勝率 63.5%、CAGR 約 21%、MDD −21%（大盤 +403%、MDD −32%）。對股票池等權買進持有報酬較差、回撤較小。
- 五年十檔等權成績仍在 `reports\`（舊規則 1 張）。

---

## 7. 注意

- 要有網路（Yahoo、Google News）。報價可能延遲。
- 紙上 ≠ 實盤。世紀單檔會扭曲五年報酬。2021–2026 是半導體大多頭。

