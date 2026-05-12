"""
options/pricing.py

Black-Scholes option pricer used as simulation fallback
when OptionMetrics data is not available.
"""

import numpy as np
from scipy.stats import norm
from dataclasses import dataclass
from typing import Literal


@dataclass
class OptionContract:
    option_type: Literal["put", "call"]
    spot: float
    strike: float
    dte: int           # days to expiry
    iv: float          # annualized implied vol (e.g. 0.20 = 20%)
    risk_free: float   # annualized (e.g. 0.05)
    price: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0


def _d1_d2(S, K, T, r, sigma):
    if T <= 0 or sigma <= 0:
        return np.nan, np.nan
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return d1, d2


def bs_price(contract: OptionContract) -> OptionContract:
    """Price an option using Black-Scholes and populate greeks."""
    S = contract.spot
    K = contract.strike
    T = contract.dte / 365.0
    r = contract.risk_free
    sigma = contract.iv

    d1, d2 = _d1_d2(S, K, T, r, sigma)

    if np.isnan(d1):
        contract.price = max(0.0, K - S) if contract.option_type == "put" else max(0.0, S - K)
        return contract

    if contract.option_type == "put":
        contract.price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        contract.delta = -norm.cdf(-d1)
    else:
        contract.price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        contract.delta = norm.cdf(d1)

    contract.gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    contract.theta = (
        -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
        + r * K * np.exp(-r * T) * norm.cdf(-d2)
    ) / 365
    contract.vega  = S * norm.pdf(d1) * np.sqrt(T) / 100  # per 1% IV move

    return contract


def price_long_put(spot: float, dte: int, iv: float, risk_free: float,
                   strike_pct: float = 0.95) -> OptionContract:
    """Price an OTM long put. strike_pct=0.95 → 5% OTM."""
    c = OptionContract(
        option_type="put",
        spot=spot,
        strike=round(spot * strike_pct, 2),
        dte=dte,
        iv=iv,
        risk_free=risk_free,
    )
    return bs_price(c)


def price_put_spread(spot: float, dte: int, iv: float, risk_free: float,
                     long_strike_pct: float = 0.95,
                     short_strike_pct: float = 0.90) -> dict:
    """
    Price a bear put spread: long put at long_strike_pct, short put at short_strike_pct.
    Returns dict with long_leg, short_leg, net_debit, max_profit, breakeven.
    """
    long_leg = price_long_put(spot, dte, iv, risk_free, long_strike_pct)

    short_c = OptionContract(
        option_type="put",
        spot=spot,
        strike=round(spot * short_strike_pct, 2),
        dte=dte,
        iv=iv,
        risk_free=risk_free,
    )
    short_leg = bs_price(short_c)

    net_debit  = long_leg.price - short_leg.price
    max_profit = (long_leg.strike - short_leg.strike) - net_debit
    breakeven  = long_leg.strike - net_debit

    return {
        "long_leg":   long_leg,
        "short_leg":  short_leg,
        "net_debit":  net_debit,
        "max_profit": max_profit,
        "breakeven":  breakeven,
    }


def put_pnl_at_expiry(contract: OptionContract, spot_at_expiry: float) -> float:
    """P&L of a long put at expiry given spot price."""
    intrinsic = max(0.0, contract.strike - spot_at_expiry)
    return intrinsic - contract.price


def spread_pnl_at_expiry(spread: dict, spot_at_expiry: float) -> float:
    """P&L of a bear put spread at expiry given spot price."""
    long_intrinsic  = max(0.0, spread["long_leg"].strike  - spot_at_expiry)
    short_intrinsic = max(0.0, spread["short_leg"].strike - spot_at_expiry)
    return (long_intrinsic - short_intrinsic) - spread["net_debit"]
