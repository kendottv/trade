"""Data loading and public-source price fetching (AC-2, AC-4, AC-15, AC-17).

- NN3 monthly returns are read from the supplied CSV; the main strategy column is used.
- TWII is read from the repo's snr_backtest/data/TWII.csv.
- Point-in-time universe from inputs/tw50_membership_intervals.csv (left-closed, right-open).
- 87 non-TEJ codes + 0050 + 00632R: yfinance period=max, auto_adjust=True;
  try {code}.TW then {code}.TWO; cache under data/ (never cache TEJ). Skip download if CSV already exists.
- 6 TEJ-only codes (2311, 2325, 3474, 3697, 2823, 2888): read the two gitignored
  text files (UTF-16 or UTF-8, tab-separated). Only three columns are kept.
  Verify against inputs/tej_manifest.csv; mismatch stops with printed diffs.
- Missing TEJ files raise before any fetch or calculation, with the full required message.
  Paths are read from config at call time so tests can patch them.
- No mixing of yfinance and TEJ prices for the same code.
"""
from pathlib import Path
from typing import Iterable

import pandas as pd
import yfinance as yf

from .config import (
    DATA_DIR,
    DEFAULT_NN_OUT_DIR,
    MAIN_STRATEGY_COL,
    TWII_PATH,
    MEMBERSHIP_CSV,
    TEJ_MANIFEST_CSV,
    TEJ_STOCK_CODES,
)


def normalize_symbol(code: str) -> str:
    """Legacy helper: ensure .TW suffix. Prefer explicit suffix for .TWO cases."""
    c = str(code).strip().upper()
    if not c.endswith(".TW") and not c.endswith(".TWO"):
        c = c + ".TW"
    return c


def load_nn3_monthly(nn_out_dir: Path | str | None = None) -> pd.Series:
    """Load the main-strategy monthly return series from portfolio_monthly.csv."""
    if nn_out_dir is None:
        nn_out_dir = DEFAULT_NN_OUT_DIR
    path = Path(nn_out_dir) / "portfolio_monthly.csv"
    if not path.exists():
        raise FileNotFoundError(f"NN3 monthly file not found: {path}")
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    if MAIN_STRATEGY_COL not in df.columns:
        raise KeyError(f"Column '{MAIN_STRATEGY_COL}' missing from {path}")
    s = df[MAIN_STRATEGY_COL].astype(float)
    s.name = "NN3"
    return s.sort_index()


def load_twii(twii_path: Path | str | None = None) -> pd.DataFrame:
    """Load TWII daily OHLCV from the repo CSV."""
    path = Path(twii_path) if twii_path else TWII_PATH
    if not path.exists():
        raise FileNotFoundError(f"TWII file not found: {path}")
    df = pd.read_csv(path, parse_dates=["Date"])
    df = df.set_index("Date").sort_index()
    return df


def load_membership_intervals(path: Path | str | None = None) -> pd.DataFrame:
    """Load point-in-time membership intervals."""
    p = Path(path) if path else MEMBERSHIP_CSV
    if not p.exists():
        raise FileNotFoundError(f"Membership intervals file not found: {p}")
    df = pd.read_csv(p, parse_dates=["start_date", "end_date"])
    df["code"] = df["code"].astype(str).str.strip()
    return df


def constituents_on_date(
    date: str | pd.Timestamp,
    membership: pd.DataFrame | None = None,
) -> list[str]:
    """Return sorted unique codes that are constituents on the given date (left-closed, right-open)."""
    if membership is None:
        membership = load_membership_intervals()
    d = pd.to_datetime(date)
    mask = (membership["start_date"] <= d) & (
        membership["end_date"].isna() | (d < membership["end_date"])
    )
    codes = membership.loc[mask, "code"].unique().tolist()
    return sorted(codes)


def check_tej_files_exist() -> None:
    """Raise FileNotFoundError with the full AC-17 message if any TEJ file is missing.
    Reads paths from config module at call time (patchable).
    """
    import research.strategy_combo.config as cfg

    missing = []
    paths = {
        "tej_prices_a.txt": cfg.TEJ_PRICES_A,
        "tej_prices_b.txt": cfg.TEJ_PRICES_B,
    }
    for name, path in paths.items():
        if not Path(path).exists():
            missing.append((name, Path(path).resolve()))
    if missing:
        missing_names = ", ".join(n for n, _ in missing)
        missing_paths = "\n".join(f"  {n}: {p}" for n, p in missing)
        msg = (
            f"缺少 TEJ 價格檔案：{missing_names}。\n"
            f"應放置的完整路徑：\n{missing_paths}\n"
            f"目錄：{cfg.TEJ_INPUT_DIR.resolve()}\n"
            "資料來源：TEJ「調整股價(日)-除權息調整」，範圍必須包含下市股票，"
            "代碼為 2311、2325、3474、3697、2823、2888。\n"
            "原始匯出檔在 Kendo 桌面的資料夾：TEJ20261117104345（tej_prices_a.txt）"
            "與 TEJ20261117104518（tej_prices_b.txt）。\n"
            "這些檔案已被 .gitignore 排除，不可 commit。\n"
            "不可改用 yfinance 代替、不可略過這 6 檔、不可退回使用目前成分股名單。"
        )
        raise FileNotFoundError(msg)


def _read_tej_raw(path: Path) -> pd.DataFrame:
    """Read a TEJ export (UTF-16 LE+BOM or UTF-8). Return the raw DataFrame."""
    encodings = ["utf-16", "utf-8-sig", "utf-8"]
    last_err: Exception | None = None
    for enc in encodings:
        try:
            df = pd.read_csv(path, sep="\t", encoding=enc, dtype=str, low_memory=False)
            if all(c in df.columns for c in ("證券代碼", "年月日", "收盤價(元)")):
                return df
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    raise RuntimeError(f"無法讀取 TEJ 檔 {path}（編碼嘗試失敗）: {last_err}")


def _process_tej_df(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only the three required columns; normalize code and date; coerce price."""
    df = df[["證券代碼", "年月日", "收盤價(元)"]].copy()
    df["code"] = df["證券代碼"].astype(str).str.split(n=1).str[0].str.strip()
    df["date"] = pd.to_datetime(df["年月日"], format="%Y%m%d", errors="coerce")
    df["close"] = pd.to_numeric(df["收盤價(元)"], errors="coerce")
    out = df[["code", "date", "close"]].dropna(subset=["code", "date", "close"])
    return out.sort_values(["code", "date"]).reset_index(drop=True)


def load_and_verify_tej_prices() -> dict[str, pd.Series]:
    """Load both TEJ files, verify against manifest, return {code: close Series}."""
    check_tej_files_exist()
    if not TEJ_MANIFEST_CSV.exists():
        raise FileNotFoundError(f"tej_manifest.csv missing: {TEJ_MANIFEST_CSV}")

    import research.strategy_combo.config as cfg
    manifest = pd.read_csv(TEJ_MANIFEST_CSV)
    required_cols = {"source_file", "code", "n_obs", "start_date", "end_date"}
    if not required_cols.issubset(manifest.columns):
        raise ValueError(f"tej_manifest.csv missing columns: {required_cols - set(manifest.columns)}")

    a_proc = _process_tej_df(_read_tej_raw(cfg.TEJ_PRICES_A))
    b_proc = _process_tej_df(_read_tej_raw(cfg.TEJ_PRICES_B))
    files_data = {
        "tej_prices_a.txt": a_proc,
        "tej_prices_b.txt": b_proc,
    }

    diffs: list[str] = []
    for _, row in manifest.iterrows():
        fname = str(row["source_file"])
        code = str(row["code"]).strip()
        expected_n = int(row["n_obs"])
        expected_start = pd.to_datetime(row["start_date"])
        expected_end = pd.to_datetime(row["end_date"])
        if fname not in files_data:
            diffs.append(f"manifest 引用未知檔案 {fname}")
            continue
        sub = files_data[fname][files_data[fname]["code"] == code]
        actual_n = len(sub)
        if actual_n == 0:
            diffs.append(f"{fname} 缺少代碼 {code}")
            continue
        actual_start = sub["date"].min()
        actual_end = sub["date"].max()
        if actual_n != expected_n:
            diffs.append(f"{fname} {code} 筆數不符：期望 {expected_n}，實際 {actual_n}")
        if actual_start != expected_start:
            diffs.append(
                f"{fname} {code} 起始日不符：期望 {expected_start.date()}，實際 {actual_start.date()}"
            )
        if actual_end != expected_end:
            diffs.append(
                f"{fname} {code} 結束日不符：期望 {expected_end.date()}，實際 {actual_end.date()}"
            )

    for fname, proc in files_data.items():
        actual_codes = set(proc["code"].unique())
        expected_codes = set(
            manifest.loc[manifest["source_file"] == fname, "code"].astype(str).str.strip()
        )
        extra = actual_codes - expected_codes
        missing = expected_codes - actual_codes
        if extra:
            diffs.append(f"{fname} 有多餘代碼：{sorted(extra)}")
        if missing:
            diffs.append(f"{fname} 缺少代碼：{sorted(missing)}")

    if diffs:
        print("TEJ 與 manifest 不一致：")
        for d in diffs:
            print(d)
        raise RuntimeError("TEJ 資料與 tej_manifest.csv 不符，已停止。")

    combined = pd.concat([a_proc, b_proc], ignore_index=True)
    prices: dict[str, pd.Series] = {}
    for code, grp in combined.groupby("code"):
        s = grp.set_index("date")["close"].sort_index()
        if s.index.duplicated().any():
            raise ValueError(f"代碼 {code} 出現重複日期")
        prices[str(code)] = s
    return prices


def fetch_yfinance_prices(
    codes: Iterable[str],
    data_dir: Path | str | None = None,
) -> dict[str, pd.DataFrame]:
    """Download adjusted daily prices for non-TEJ codes (4-digit).
    Tries {code}.TW then {code}.TWO. Skips download if a CSV already exists.
    """
    if data_dir is None:
        data_dir = DATA_DIR
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, pd.DataFrame] = {}
    for raw in codes:
        code = str(raw).strip()
        if code in TEJ_STOCK_CODES:
            raise ValueError(f"代碼 {code} 為 TEJ 專用，禁止使用 yfinance")
        # skip if already cached
        existing_sym = None
        for suf in (".TW", ".TWO"):
            p = data_dir / f"{code}{suf}.csv"
            if p.exists():
                existing_sym = f"{code}{suf}"
                break
        if existing_sym:
            df = pd.read_csv(data_dir / f"{existing_sym}.csv", index_col=0, parse_dates=True)
            results[existing_sym] = df
            continue

        success = False
        for suf in (".TW", ".TWO"):
            sym = f"{code}{suf}"
            try:
                df = yf.download(sym, period="max", auto_adjust=True, progress=False)
                if df is None or df.empty:
                    continue
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                out_path = data_dir / f"{sym}.csv"
                df.to_csv(out_path)
                results[sym] = df
                success = True
                break
            except Exception:  # noqa: BLE001
                continue
        if not success:
            raise RuntimeError(f"yfinance 無法取得 {code}（.TW 與 .TWO 皆失敗）")
    return results


def load_price_csv(symbol: str, data_dir: Path | str | None = None) -> pd.DataFrame:
    """Load a previously saved yfinance CSV. symbol must include the suffix (.TW or .TWO)."""
    if data_dir is None:
        data_dir = DATA_DIR
    path = Path(data_dir) / f"{symbol}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Price file not found: {path}")
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return df.sort_index()


def get_close_series(
    code: str,
    data_dir: Path | str | None = None,
    tej_prices: dict[str, pd.Series] | None = None,
) -> pd.Series:
    """Return the close Series for a 4-digit code."""
    code = str(code).strip()
    if code in TEJ_STOCK_CODES:
        if tej_prices is None:
            tej_prices = load_and_verify_tej_prices()
        if code not in tej_prices:
            raise KeyError(f"TEJ 價格缺少代碼 {code}")
        return tej_prices[code]
    for suf in (".TW", ".TWO"):
        try:
            df = load_price_csv(f"{code}{suf}", data_dir)
            col = "Close" if "Close" in df.columns else df.columns[0]
            return df[col].sort_index()
        except FileNotFoundError:
            continue
    raise FileNotFoundError(f"找不到 {code} 的 yfinance 快取（.TW / .TWO）")
