# NN3 60% + CTA A1 40% 紙上 / 模擬組合（v4）回滾說明

## 切換前備份位置

部署後第一次遇到新的 NN3 月目標時，程式會自動把當時的

- `paper_nn/account.json`
- `paper_nn/ledger.csv`
- `paper_nn/equity.csv`
- `paper_nn/daily_log.md`

複製到 repo 外面的

`C:\Users\AUSER\trade_backups\paper_combo\backup_pre_combo_<YYYYMMDD-HHMMSS>\`

並寫入 `manifest.txt`（每檔 sha256）。該資料夾已存在時不會覆寫。

## 回滾步驟（AC-15）

1. **先放停止開關**  
   在 `snr_backtest/paper_nn/` 建立空檔 `SIM_STOP`。模擬端任何送單／對帳都會立刻停止。

2. **封存目前紙上檔（不刪）**  
   把目前的  
   `account.json`、`ledger.csv`、`equity.csv`、`daily_log.md`、`a1_signal.json`、`a1_signals.csv`  
   移到  
   `C:\Users\AUSER\trade_backups\paper_combo\rollback_archive_<YYYYMMDD-HHMMSS>\`  
   （資料夾不存在時自己建立）。不要刪除。

3. **從備份還原**  
   從最近的 `backup_pre_combo_*` 把四個檔案複製回 `paper_nn\`。  
   用該資料夾內 `manifest.txt` 的 sha256 核對每個複本與備份檔相同。

4. **程式碼**  
   由砍豆決定（例如 `git revert` 或切回 base commit）。**不要 force push**。

5. **模擬帳戶與 sim_state.json**  
   - 模擬帳戶裡 A1 買進的 0050 如何處理（賣出、保留、或手動調整）由砍豆決定。  
   - `sim_state.json` 的 `baseline.legacy_positions` 保持原樣（規格要求不改）。  
   - 程式**不會**自動處理模擬帳戶或還原 `sim_state.json`。回滾後舊程式會再次把 0050 視為 legacy，因此**一定要先放 SIM_STOP**。

6. **確認**  
   在 `snr_backtest` 用 `.venv` 執行：  
   `python nn_paper.py --status`  
   確認策略回到切換前狀態、權益曲線接回。

## 注意

- 回滾後，切換期間的紙上紀錄只留在 `rollback_archive_*` 資料夾，不會自動合併回主帳戶。
- `a1_signal.json` / `a1_signals.csv` 與更新後的 `data/TWII.csv` 會被 `git_daily.bat` 推到公開 repo（內容只有指數與訊號）。
- 本說明不涉及真實下單。所有模擬送單仍只走 `sim_trader.login()` + `safe_place()`，`SIMULATION_ONLY = True`。
