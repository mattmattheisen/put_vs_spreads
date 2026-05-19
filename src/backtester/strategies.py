"""
backtester/strategies.py

Strategy classes: LongPut and PutSpread.
Each strategy is opened on entry_signal and closed on exit_signal or ROLL_DTE.

TEMPORAL INTEGRITY NOTES
─────────────────────────────────────────────────────────────────────────────
The .open() method now accepts two spot/IV pairs:

    signal_spot / signal_iv  — the bar that *generated* the signal (t-1)
                               Used only for informational storage in Trade.

    exec_spot / exec_iv      — the bar on which execution occurs (t, next open)
                               Used for all pricing and P&L calculations.

BROKEN (original):  lp.open(date, spot, iv, regime)
    → spot and iv were the signal bar's close, used for pricing.
    → Implies we filled at yesterday's close price — impossible.

FIXED:              lp.open(date, exec_spot, exec_iv, regime, signal_spot)
    → exec_spot/exec_iv are today's open-bar values (or prior close as proxy).
    → signal_spot stored for reference only (not used in P&L math).
─────────────────────────────────────────────────────────────────────────────
"""

from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
import numpy as np
from config import (
    DTE_TARGET, ROLL_DTE, PUT_STRIKE_PCT, SHORT_STRIKE_PCT,
    RISK_FREE_RATE, POSITION_SIZE,
)
from src.options.pricing import (
    price_long_put, price_put_spread,
    put_pnl_at_expiry, spread_pnl_at_expiry,
    OptionContract,
)


@dataclass
class Trade:
    strategy:      str
    open_date:     pd.Timestamp
    close_date:    Optional[pd.Timestamp]
    signal_spot:   float                   # spot on signal bar (informational)
    open_spot:     float                   # spot at execution (next-bar open)
    close_spot:    Optional[float]
    premium_paid:  float                   # total debit at open (positive = cost)
    pnl:           float                   # realized P&L (positive = profit)
    regime:        str
    close_reason:  str                     # "expiry" | "roll" | "exit_signal" | "end_of_sample"
    contracts:     int = POSITION_SIZE

    @property
    def return_on_premium(self) -> float:
        if self.premium_paid == 0:
            return 0.0
        return self.pnl / self.premium_paid

    @property
    def spot_move_pct(self) -> float:
        """Move from execution open to close."""
        if self.open_spot == 0 or self.close_spot is None:
            return 0.0
        return (self.close_spot - self.open_spot) / self.open_spot


class LongPutStrategy:
    """
    Buy a single OTM put at entry. Hold to roll/expiry/exit.

    TEMPORAL INTEGRITY
    ──────────────────
    .open() prices the option using exec_spot and exec_iv — the values
    available at the *execution* bar's open, not the signal bar's close.
    In bs_sim mode this is the prior day's close (a conservative, realistic
    proxy for next-morning fill). With real data, use the actual open price.
    """
    name = "LongPut"

    def __init__(self):
        self.open_contract: Optional[OptionContract] = None
        self.open_date:     Optional[pd.Timestamp]   = None
        self.open_spot:     float = 0.0
        self.signal_spot:   float = 0.0
        self.open_regime:   str   = ""
        self.days_held:     int   = 0

    def is_open(self) -> bool:
        return self.open_contract is not None

    def open(
        self,
        date:        pd.Timestamp,
        exec_spot:   float,
        exec_iv:     float,
        regime:      str,
        signal_spot: float = 0.0,    # informational only — not used in pricing
    ) -> None:
        """
        Price and open the position using exec_spot/exec_iv (next-bar values).
        signal_spot stored for Trade record only.
        """
        self.open_contract = price_long_put(
            exec_spot, DTE_TARGET, exec_iv, RISK_FREE_RATE, PUT_STRIKE_PCT
        )
        self.open_date   = date
        self.open_spot   = exec_spot
        self.signal_spot = signal_spot
        self.open_regime = regime
        self.days_held   = 0

    def step(self) -> None:
        self.days_held += 1

    def should_roll(self) -> bool:
        if self.open_contract is None:
            return False
        remaining = DTE_TARGET - self.days_held
        return remaining <= ROLL_DTE

    def close(self, date: pd.Timestamp, spot: float, reason: str) -> Trade:
        pnl     = put_pnl_at_expiry(self.open_contract, spot) * POSITION_SIZE * 100
        premium = self.open_contract.price * POSITION_SIZE * 100
        trade = Trade(
            strategy=self.name,
            open_date=self.open_date,
            close_date=date,
            signal_spot=self.signal_spot,
            open_spot=self.open_spot,
            close_spot=spot,
            premium_paid=premium,
            pnl=pnl,
            regime=self.open_regime,
            close_reason=reason,
            contracts=POSITION_SIZE,
        )
        self.open_contract = None
        self.open_date     = None
        self.open_spot     = 0.0
        self.signal_spot   = 0.0
        self.days_held     = 0
        return trade


class PutSpreadStrategy:
    """
    Buy an OTM put and sell a further OTM put (bear put spread) at entry.

    TEMPORAL INTEGRITY — same as LongPutStrategy above.
    """
    name = "PutSpread"

    def __init__(self):
        self.open_spread:  Optional[dict]          = None
        self.open_date:    Optional[pd.Timestamp]  = None
        self.open_spot:    float = 0.0
        self.signal_spot:  float = 0.0
        self.open_regime:  str   = ""
        self.days_held:    int   = 0

    def is_open(self) -> bool:
        return self.open_spread is not None

    def open(
        self,
        date:        pd.Timestamp,
        exec_spot:   float,
        exec_iv:     float,
        regime:      str,
        signal_spot: float = 0.0,
    ) -> None:
        self.open_spread = price_put_spread(
            exec_spot, DTE_TARGET, exec_iv, RISK_FREE_RATE,
            PUT_STRIKE_PCT, SHORT_STRIKE_PCT,
        )
        self.open_date   = date
        self.open_spot   = exec_spot
        self.signal_spot = signal_spot
        self.open_regime = regime
        self.days_held   = 0

    def step(self) -> None:
        self.days_held += 1

    def should_roll(self) -> bool:
        if self.open_spread is None:
            return False
        remaining = DTE_TARGET - self.days_held
        return remaining <= ROLL_DTE

    def close(self, date: pd.Timestamp, spot: float, reason: str) -> Trade:
        pnl     = spread_pnl_at_expiry(self.open_spread, spot) * POSITION_SIZE * 100
        premium = self.open_spread["net_debit"] * POSITION_SIZE * 100
        trade = Trade(
            strategy=self.name,
            open_date=self.open_date,
            close_date=date,
            signal_spot=self.signal_spot,
            open_spot=self.open_spot,
            close_spot=spot,
            premium_paid=premium,
            pnl=pnl,
            regime=self.open_regime,
            close_reason=reason,
            contracts=POSITION_SIZE,
        )
        self.open_spread = None
        self.open_date   = None
        self.open_spot   = 0.0
        self.signal_spot = 0.0
        self.days_held   = 0
        return trade
