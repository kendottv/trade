"""Two strategy families, each with an optional Kaufman SNR regime gate.

SNR_n (訊噪比 / Kaufman efficiency ratio), n=20:

    SNR_t = abs(close_t - close_{t-n}) / sum_{i=t-n+1..t} abs(close_i - close_{i-1})

If the denominator is 0, SNR = 0. Rolling windows use data through t only.

A) breakout_v1
   Signal at t close: close_t > max(high of prior 20 days)  [window t-20 .. t-1]
   AND (if gated) SNR_20 >= 0.4
   Fill: next open.
   Exit: TP +25% / SL -20% vs fill (intrabar; if both, SL first).
         Time stop: close below min(low of prior 20 days) for 3 consecutive
         closes → sell next open.
   No TWII insurance (the old one was path-dependent / buggy).

B) pullback_v1
   Uptrend: close > SMA(60)
   Pullback: close in [0.97, 1.01] * SMA(20)  (price has retraced toward the 20-SMA)
   AND (if gated) SNR_20 <= 0.25  (choppy / mean-revert regime)
   Fill: next open.
   Exit: TP +8% / SL -4% vs fill (intrabar; if both, SL first).
   No time stop, no TWII.

C) breakout_v2  (parameterized; see make_breakout_v2 / config.BREAKOUT_V2_*)
   Core breakout + SNR gate, plus optional:
     snr_rising  — SNR_20 > SMA(SNR_20, 5)
     vol_mult    — volume >= vol_mult * volume_sma_20  (0 = off)
     twii_filter — ^TWII close > ^TWII SMA 60
     no_chase    — skip if close > prior 20-day high * chase_mult (default 1.08)
     trail       — once unrealized (bar high vs fill) >= 12%, exit next open
                   if close < prior 15-day low (in addition to hard TP/SL)

Raw (no-SNR) twins exist so comparison.md can show whether the gate helped.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from config import (
    BREAKOUT_LOOKBACK,
    BREAKOUT_SL,
    BREAKOUT_SNR_MIN,
    BREAKOUT_TIME_STOP_DAYS,
    BREAKOUT_TP,
    BREAKOUT_V2_CHASE_MULT,
    BREAKOUT_V2_NO_CHASE,
    BREAKOUT_V2_SNR_MIN,
    BREAKOUT_V2_SNR_RISING,
    BREAKOUT_V2_SNR_SMA,
    BREAKOUT_V2_TRAIL,
    BREAKOUT_V2_TRAIL_ARM,
    BREAKOUT_V2_TRAIL_LOOKBACK,
    BREAKOUT_V2_TWII_FILTER,
    BREAKOUT_V2_VOL_MULT,
    PULLBACK_BAND_HI,
    PULLBACK_BAND_LO,
    PULLBACK_SL,
    PULLBACK_SMA_FAST,
    PULLBACK_SMA_TREND,
    PULLBACK_SNR_MAX,
    PULLBACK_TP,
    SNR_N,
)


def kaufman_snr(close: pd.Series, n: int = SNR_N) -> pd.Series:
    """Kaufman efficiency ratio. Look-ahead safe: uses close through t only."""
    close = close.astype(float)
    step = close.diff().abs()
    denom = step.rolling(n, min_periods=n).sum()
    numer = (close - close.shift(n)).abs()
    snr = numer / denom
    snr = snr.where(denom > 0, 0.0)
    return snr.fillna(0.0)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Attach look-ahead-safe columns. prior_* exclude today (shift 1)."""
    out = df.copy()
    h, l, c = out["High"], out["Low"], out["Close"]
    n = BREAKOUT_LOOKBACK
    # max high of bars [t-n, t-1]  ==  high.shift(1).rolling(n).max()
    out["prior_high_20"] = h.shift(1).rolling(n, min_periods=n).max()
    out["prior_low_20"] = l.shift(1).rolling(n, min_periods=n).min()
    out["prior_low_15"] = l.shift(1).rolling(15, min_periods=15).min()
    out["sma_20"] = c.rolling(PULLBACK_SMA_FAST, min_periods=PULLBACK_SMA_FAST).mean()
    out["sma_60"] = c.rolling(PULLBACK_SMA_TREND, min_periods=PULLBACK_SMA_TREND).mean()
    out["snr_20"] = kaufman_snr(c, SNR_N)
    out["snr_sma_5"] = out["snr_20"].rolling(BREAKOUT_V2_SNR_SMA, min_periods=BREAKOUT_V2_SNR_SMA).mean()
    if "Volume" in out.columns:
        out["volume_sma_20"] = out["Volume"].rolling(n, min_periods=n).mean()
    else:
        out["volume_sma_20"] = pd.NA
    return out


@dataclass
class StrategySpec:
    name: str
    tp: float  # +0.25 means +25%
    sl: float  # +0.20 means -20%
    time_stop_days: int  # 0 = disabled
    use_snr: bool
    kind: str  # "breakout" | "pullback" | "macd" | "rsi" | "kd" | "sma" | "bb"
    # --- breakout_v2 optional flags (v1 leaves these at defaults) ---
    snr_min: float | None = None  # None → BREAKOUT_SNR_MIN when use_snr
    snr_max: float | None = None  # pullback SNR ceiling
    snr_rising: bool = False
    vol_mult: float = 0.0  # 0 = off
    twii_filter: bool = False
    no_chase: bool = False
    chase_mult: float = 1.08
    trail: bool = False
    trail_arm: float = 0.12
    trail_lookback: int = 15
    lookback: int = 20
    sma_fast: int = 20
    sma_trend: int = 60
    band_lo: float = 0.97
    band_hi: float = 1.01
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    rsi_n: int = 14
    rsi_os: float = 30.0
    rsi_ob: float = 70.0
    kd_n: int = 9
    kd_k: int = 3
    kd_d: int = 3
    kd_os: float = 20.0
    kd_ob: float = 80.0
    bb_n: int = 20
    bb_k: float = 2.0
    bb_mode: str = "revert"  # revert = 碰下軌買；break = 收上軌買

    def entry_signal(self, row: pd.Series) -> bool:
        if self.kind in ("breakout", "pullback"):
            if pd.isna(row.get("snr_20")):
                return False
        snr = float(row["snr_20"]) if pd.notna(row.get("snr_20")) else 0.0
        if self.kind == "breakout":
            prior = row.get("prior_high_20")
            if pd.isna(prior):
                return False
            close = float(row["Close"])
            prior_f = float(prior)
            if not (close > prior_f):
                return False
            threshold = self.snr_min if self.snr_min is not None else BREAKOUT_SNR_MIN
            if self.use_snr and snr < threshold:
                return False
            if self.snr_rising:
                snr_sma = row.get("snr_sma_5")
                if pd.isna(snr_sma) or not (snr > float(snr_sma)):
                    return False
            if self.vol_mult and self.vol_mult > 0:
                vol = row.get("Volume")
                vol_sma = row.get("volume_sma_20")
                if pd.isna(vol) or pd.isna(vol_sma) or float(vol_sma) <= 0:
                    return False
                if not (float(vol) >= self.vol_mult * float(vol_sma)):
                    return False
            if self.twii_filter:
                twii_c = row.get("twii_close")
                twii_sma = row.get("twii_sma_60")
                if pd.isna(twii_c) or pd.isna(twii_sma):
                    return False
                if not (float(twii_c) > float(twii_sma)):
                    return False
            if self.no_chase:
                if close > prior_f * self.chase_mult:
                    return False
            return True
        if self.kind == "pullback":
            sma60 = row.get("sma_60")
            sma20 = row.get("sma_20")
            if pd.isna(sma60) or pd.isna(sma20) or sma20 <= 0:
                return False
            if not (row["Close"] > sma60):
                return False
            lo = sma20 * float(self.band_lo if self.band_lo else PULLBACK_BAND_LO)
            hi = sma20 * float(self.band_hi if self.band_hi else PULLBACK_BAND_HI)
            if not (lo < row["Close"] <= hi):
                return False
            ceiling = self.snr_max if self.snr_max is not None else PULLBACK_SNR_MAX
            if self.use_snr and snr > ceiling:
                return False
            return True
        if self.kind == "macd":
            m = row.get("macd")
            s = row.get("macd_sig")
            mp = row.get("macd_prev")
            sp = row.get("macd_sig_prev")
            if pd.isna(m) or pd.isna(s) or pd.isna(mp) or pd.isna(sp):
                return False
            return float(mp) <= float(sp) and float(m) > float(s)
        if self.kind == "rsi":
            r = row.get("rsi")
            rp = row.get("rsi_prev")
            if pd.isna(r) or pd.isna(rp):
                return False
            return float(rp) < float(self.rsi_os) and float(r) >= float(self.rsi_os)
        if self.kind == "kd":
            k, d = row.get("k"), row.get("d")
            kp, dp = row.get("k_prev"), row.get("d_prev")
            if pd.isna(k) or pd.isna(d) or pd.isna(kp) or pd.isna(dp):
                return False
            golden = float(kp) <= float(dp) and float(k) > float(d)
            return golden and float(k) < float(self.kd_os)
        if self.kind == "sma":
            f, s = row.get("sma_fast"), row.get("sma_slow")
            fp, sp = row.get("sma_fast_prev"), row.get("sma_slow_prev")
            if pd.isna(f) or pd.isna(s) or pd.isna(fp) or pd.isna(sp):
                return False
            return float(fp) <= float(sp) and float(f) > float(s)
        if self.kind == "bb":
            c = row.get("Close")
            up, lo, mid = row.get("bb_up"), row.get("bb_lo"), row.get("bb_mid")
            if pd.isna(c) or pd.isna(up) or pd.isna(lo) or pd.isna(mid):
                return False
            if (self.bb_mode or "revert") == "break":
                return float(c) > float(up)
            return float(c) <= float(lo)
        return False

    def time_stop_trigger(self, row: pd.Series) -> bool:
        """True on a close that counts toward the 3-day consecutive stop."""
        if self.time_stop_days <= 0:
            return False
        prior_low = row.get("prior_low_20")
        if pd.isna(prior_low):
            return False
        return row["Close"] < prior_low

    def trail_trigger(self, row: pd.Series) -> bool:
        """True when close < prior 15-day low (caller must have armed the trail)."""
        if not self.trail:
            return False
        prior_low = row.get("prior_low_15")
        if pd.isna(prior_low):
            return False
        return float(row["Close"]) < float(prior_low)

    def param_dict(self) -> dict:
        return {
            "snr_min": self.snr_min if self.snr_min is not None else (BREAKOUT_SNR_MIN if self.use_snr else 0.0),
            "snr_rising": bool(self.snr_rising),
            "vol_mult": float(self.vol_mult or 0.0),
            "twii_filter": bool(self.twii_filter),
            "no_chase": bool(self.no_chase),
            "trail": bool(self.trail),
        }


def make_breakout_v2(
    snr_min: float | None = None,
    snr_rising: bool | None = None,
    vol_mult: float | None = None,
    twii_filter: bool | None = None,
    no_chase: bool | None = None,
    trail: bool | None = None,
    name: str = "breakout_v2",
) -> StrategySpec:
    """Parameterized breakout. None → config.BREAKOUT_V2_* defaults."""
    return StrategySpec(
        name=name,
        tp=BREAKOUT_TP,
        sl=BREAKOUT_SL,
        time_stop_days=BREAKOUT_TIME_STOP_DAYS,
        use_snr=True,
        kind="breakout",
        snr_min=BREAKOUT_V2_SNR_MIN if snr_min is None else snr_min,
        snr_rising=BREAKOUT_V2_SNR_RISING if snr_rising is None else snr_rising,
        vol_mult=BREAKOUT_V2_VOL_MULT if vol_mult is None else vol_mult,
        twii_filter=BREAKOUT_V2_TWII_FILTER if twii_filter is None else twii_filter,
        no_chase=BREAKOUT_V2_NO_CHASE if no_chase is None else no_chase,
        chase_mult=BREAKOUT_V2_CHASE_MULT,
        trail=BREAKOUT_V2_TRAIL if trail is None else trail,
        trail_arm=BREAKOUT_V2_TRAIL_ARM,
        trail_lookback=BREAKOUT_V2_TRAIL_LOOKBACK,
    )


def all_strategies() -> list[StrategySpec]:
    """Breakout/pullback (+SNR/raw) plus classic indicator strategies."""
    return [
        StrategySpec(
            name="breakout_v1",
            tp=BREAKOUT_TP,
            sl=BREAKOUT_SL,
            time_stop_days=BREAKOUT_TIME_STOP_DAYS,
            use_snr=True,
            kind="breakout",
        ),
        StrategySpec(
            name="pullback_v1",
            tp=PULLBACK_TP,
            sl=PULLBACK_SL,
            time_stop_days=0,
            use_snr=True,
            kind="pullback",
        ),
        StrategySpec(
            name="breakout_raw",
            tp=BREAKOUT_TP,
            sl=BREAKOUT_SL,
            time_stop_days=BREAKOUT_TIME_STOP_DAYS,
            use_snr=False,
            kind="breakout",
        ),
        StrategySpec(
            name="pullback_raw",
            tp=PULLBACK_TP,
            sl=PULLBACK_SL,
            time_stop_days=0,
            use_snr=False,
            kind="pullback",
        ),
        # classic indicators (engine already supports these kinds)
        StrategySpec(
            name="macd_v1",
            tp=0.15,
            sl=0.08,
            time_stop_days=0,
            use_snr=False,
            kind="macd",
        ),
        StrategySpec(
            name="rsi_v1",
            tp=0.12,
            sl=0.06,
            time_stop_days=0,
            use_snr=False,
            kind="rsi",
        ),
        StrategySpec(
            name="kd_v1",
            tp=0.12,
            sl=0.06,
            time_stop_days=0,
            use_snr=False,
            kind="kd",
        ),
        StrategySpec(
            name="sma_cross_v1",
            tp=0.15,
            sl=0.08,
            time_stop_days=0,
            use_snr=False,
            kind="sma",
        ),
        StrategySpec(
            name="bb_revert_v1",
            tp=0.10,
            sl=0.06,
            time_stop_days=0,
            use_snr=False,
            kind="bb",
            bb_mode="revert",
        ),
    ]
