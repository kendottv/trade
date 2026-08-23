"""Persistent virtual paper account under paper/ (or paper/replay/).

NOT a real broker. State files:
- account.json  cash, equity, positions, pending, last_session
- ledger.csv    every fill
- equity.csv    daily mark-to-market
- daily_log.md  human summary for the run
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

from config import INITIAL_CAPITAL, ROOT

TAIPEI = timezone(timedelta(hours=8))

LEDGER_COLS = [
    "date", "ticker", "action", "reason", "price", "shares", "cash", "equity", "snr",
]
EQUITY_COLS = ["date", "cash", "market_value", "equity"]


def taipei_now_iso() -> str:
    return datetime.now(TAIPEI).strftime("%Y-%m-%d %H:%M:%S%z")


@dataclass
class PaperPosition:
    ticker: str
    name: str
    shares: int
    avg_price: float
    entry_date: str
    entry_snr: float | None = None
    time_stop_count: int = 0
    trail_armed: bool = False


@dataclass
class PaperPending:
    side: str  # buy | sell
    ticker: str
    name: str
    reason: str
    snr: float | None = None
    signal_date: str = ""
    target_weight: float | None = None
    name_heat: float | None = None
    name_trend: str = ""
    name_lock: bool = False
    size_note: str = ""


@dataclass
class PaperAccount:
    cash: float = INITIAL_CAPITAL
    equity: float = INITIAL_CAPITAL
    positions: list = field(default_factory=list)
    pending: list = field(default_factory=list)
    updated_at: str = ""
    last_session: str | None = None
    initial_cash: float = INITIAL_CAPITAL

    def held_tickers(self):
        return {p.ticker for p in self.positions if p.shares > 0}

    def pending_tickers(self, side=None):
        out = set()
        for p in self.pending:
            if side is None or p.side == side:
                out.add(p.ticker)
        return out

    def get_position(self, ticker):
        for p in self.positions:
            if p.ticker == ticker:
                return p
        return None

    def drop_position(self, ticker):
        kept = []
        found = None
        for p in self.positions:
            if p.ticker == ticker:
                found = p
            else:
                kept.append(p)
        self.positions = kept
        return found

    def drop_pending(self, ticker, side=None):
        kept = []
        dropped = []
        for p in self.pending:
            if p.ticker == ticker and (side is None or p.side == side):
                dropped.append(p)
            else:
                kept.append(p)
        self.pending = kept
        return dropped

    def has_pending(self, ticker, side):
        return any(p.ticker == ticker and p.side == side for p in self.pending)


def account_to_dict(acct):
    return {
        "cash": round(float(acct.cash), 2),
        "equity": round(float(acct.equity), 2),
        "positions": [
            {
                "ticker": p.ticker,
                "name": p.name,
                "shares": int(p.shares),
                "avg_price": round(float(p.avg_price), 4),
                "entry_date": p.entry_date,
                "entry_snr": (None if p.entry_snr is None else round(float(p.entry_snr), 4)),
                "time_stop_count": int(p.time_stop_count),
                "trail_armed": bool(getattr(p, "trail_armed", False)),
            }
            for p in acct.positions
        ],
        "pending": [
            {
                "side": p.side,
                "ticker": p.ticker,
                "name": p.name,
                "reason": p.reason,
                "snr": (None if p.snr is None else round(float(p.snr), 4)),
                "signal_date": p.signal_date,
                "target_weight": p.target_weight,
                "name_heat": p.name_heat,
                "name_trend": p.name_trend,
                "name_lock": bool(p.name_lock),
                "size_note": p.size_note,
            }
            for p in acct.pending
        ],
        "updated_at": acct.updated_at or taipei_now_iso(),
        "last_session": acct.last_session,
        "initial_cash": float(acct.initial_cash),
    }


def account_from_dict(raw):
    positions = [
        PaperPosition(
            ticker=p["ticker"],
            name=p.get("name", p["ticker"]),
            shares=int(p["shares"]),
            avg_price=float(p["avg_price"]),
            entry_date=str(p["entry_date"]),
            entry_snr=(None if p.get("entry_snr") in (None, "") else float(p["entry_snr"])),
            time_stop_count=int(p.get("time_stop_count") or 0),
            trail_armed=bool(p.get("trail_armed") or False),
        )
        for p in raw.get("positions") or []
    ]
    pending = [
        PaperPending(
            side=p["side"],
            ticker=p["ticker"],
            name=p.get("name", p["ticker"]),
            reason=p.get("reason", ""),
            snr=(None if p.get("snr") in (None, "") else float(p["snr"])),
            signal_date=str(p.get("signal_date") or ""),
            target_weight=(
                None if p.get("target_weight") in (None, "") else float(p["target_weight"])
            ),
            name_heat=(None if p.get("name_heat") in (None, "") else float(p["name_heat"])),
            name_trend=str(p.get("name_trend") or ""),
            name_lock=bool(p.get("name_lock") or False),
            size_note=str(p.get("size_note") or ""),
        )
        for p in raw.get("pending") or []
    ]
    return PaperAccount(
        cash=float(raw.get("cash", INITIAL_CAPITAL)),
        equity=float(raw.get("equity", raw.get("cash", INITIAL_CAPITAL))),
        positions=positions,
        pending=pending,
        updated_at=str(raw.get("updated_at") or ""),
        last_session=raw.get("last_session"),
        initial_cash=float(raw.get("initial_cash", INITIAL_CAPITAL)),
    )


class PaperStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.account_path = self.root / "account.json"
        self.ledger_path = self.root / "ledger.csv"
        self.equity_path = self.root / "equity.csv"
        self.log_path = self.root / "daily_log.md"
        self.universe_path = self.root / "universe.csv"

    def load_or_create(self, initial_cash: float = INITIAL_CAPITAL):
        if self.account_path.exists():
            raw = json.loads(self.account_path.read_text(encoding="utf-8"))
            return account_from_dict(raw)
        acct = PaperAccount(
            cash=initial_cash,
            equity=initial_cash,
            initial_cash=initial_cash,
            updated_at=taipei_now_iso(),
        )
        self.save_account(acct)
        self._ensure_csv(self.ledger_path, LEDGER_COLS)
        self._ensure_csv(self.equity_path, EQUITY_COLS)
        return acct

    def save_account(self, acct):
        acct.updated_at = taipei_now_iso()
        self.account_path.write_text(
            json.dumps(account_to_dict(acct), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def append_ledger(self, row: dict) -> None:
        self._ensure_csv(self.ledger_path, LEDGER_COLS)
        line = {c: row.get(c, "") for c in LEDGER_COLS}
        df = pd.DataFrame([line], columns=LEDGER_COLS)
        df.to_csv(
            self.ledger_path,
            mode="a",
            header=False,
            index=False,
            encoding="utf-8-sig",
        )

    def append_equity(self, date: str, cash: float, market_value: float, equity: float) -> None:
        self._ensure_csv(self.equity_path, EQUITY_COLS)
        if self.equity_path.exists():
            try:
                old = pd.read_csv(self.equity_path, encoding="utf-8-sig")
                if "date" in old.columns:
                    old = old[old["date"].astype(str) != str(date)]
                    old.to_csv(self.equity_path, index=False, encoding="utf-8-sig")
            except Exception:
                pass
        df = pd.DataFrame(
            [{
                "date": date,
                "cash": round(cash, 2),
                "market_value": round(market_value, 2),
                "equity": round(equity, 2),
            }],
            columns=EQUITY_COLS,
        )
        header = (not self.equity_path.exists()) or self.equity_path.stat().st_size == 0
        df.to_csv(
            self.equity_path,
            mode="a",
            header=header,
            index=False,
            encoding="utf-8-sig",
        )

    def append_log(self, text: str) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(text.rstrip() + "\n\n")

    def write_log_header(self, title: str) -> None:
        if not self.log_path.exists():
            self.log_path.write_text("# " + title + "\n\n", encoding="utf-8")

    @staticmethod
    def _ensure_csv(path: Path, cols):
        if not path.exists() or path.stat().st_size == 0:
            pd.DataFrame(columns=cols).to_csv(path, index=False, encoding="utf-8-sig")


def default_live_dir() -> Path:
    return ROOT / "paper"


def default_replay_dir() -> Path:
    return ROOT / "paper" / "replay"
