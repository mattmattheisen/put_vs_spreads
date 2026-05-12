"""
tests/test_pricing.py

Unit tests for Black-Scholes pricer and P&L functions.
"""
import sys, os
sys.path.insert(0, os.path.abspath('..'))

import pytest
from src.options.pricing import (
    bs_price, OptionContract, price_long_put,
    price_put_spread, put_pnl_at_expiry, spread_pnl_at_expiry
)


def make_atm_put(spot=450, dte=30, iv=0.20):
    c = OptionContract("put", spot=spot, strike=spot, dte=dte, iv=iv, risk_free=0.05)
    return bs_price(c)


def test_put_price_positive():
    c = make_atm_put()
    assert c.price > 0

def test_put_delta_negative():
    c = make_atm_put()
    assert c.delta < 0

def test_atm_put_delta_near_half():
    # ATM put delta should be close to -0.5
    c = make_atm_put()
    assert -0.6 < c.delta < -0.4

def test_deep_itm_put_intrinsic():
    # Deep ITM put price ≈ intrinsic value
    c = OptionContract("put", spot=400, strike=500, dte=1, iv=0.20, risk_free=0.05)
    c = bs_price(c)
    assert abs(c.price - 100) < 5

def test_expired_put_zero_otm():
    c = OptionContract("put", spot=460, strike=450, dte=0, iv=0.20, risk_free=0.05)
    c = bs_price(c)
    assert c.price == 0.0

def test_put_pnl_at_expiry_win():
    c = make_atm_put(spot=450)  # strike=450
    pnl = put_pnl_at_expiry(c, spot_at_expiry=420)  # 30 pts ITM
    assert pnl > 0

def test_put_pnl_at_expiry_loss():
    c = make_atm_put(spot=450)  # strike=450
    pnl = put_pnl_at_expiry(c, spot_at_expiry=470)  # OTM at expiry
    assert pnl < 0  # lost premium

def test_spread_net_debit_less_than_long():
    spread = price_put_spread(450, 30, 0.20, 0.05, 0.95, 0.90)
    lp = price_long_put(450, 30, 0.20, 0.05, 0.95)
    assert spread["net_debit"] < lp.price

def test_spread_max_profit_capped():
    spread = price_put_spread(450, 30, 0.20, 0.05, 0.95, 0.90)
    long_k  = spread["long_leg"].strike
    short_k = spread["short_leg"].strike
    assert spread["max_profit"] < (long_k - short_k)  # net debit reduces max profit

def test_spread_pnl_capped():
    spread = price_put_spread(450, 30, 0.20, 0.05, 0.95, 0.90)
    # Massive crash — spot at 0
    pnl_crash = spread_pnl_at_expiry(spread, 0)
    assert abs(pnl_crash - spread["max_profit"]) < 0.01  # capped exactly at max_profit

def test_price_long_put_otm():
    lp = price_long_put(spot=450, dte=30, iv=0.20, risk_free=0.05, strike_pct=0.95)
    assert lp.strike == 427.5
    assert lp.price > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
