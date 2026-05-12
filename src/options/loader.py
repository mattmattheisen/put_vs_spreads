"""
options/loader.py

Loads and normalizes historical options data.

Supports:
  - OptionMetrics standardized export (CSV)
  - CBOE DataShop format
  - Black-Scholes simulation fallback via yfinance + VIX

Set DATA_MODE in config.py to switch between modes.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from config import DATA_MODE, BACKTEST_START, BACKTEST_END, UNDERLYING, RISK_FREE_RATE
from src.options.pricing import price_long_put, price_put_spread


# ── OptionMetrics Loader ───────────────────────────────────────────────────────

def load_optionmetrics(data_dir: str = "data/raw/optionmetrics/") -> pd.DataFrame:
    """
    Load OptionMetrics standardized surface export.
    Expected columns: date, ticker, expiration, strike, cp_flag, best_bid,
                      best_offer, impl_volatility, delta, open_interest, volume
    """
    path = Path(data_dir)
    files = list(path.glob("*.csv"))
    if not files:
        raise FileNotFoundError(
            f"No OptionMetrics CSVs found in {data_dir}. "
            "Export from wrds.wharton.upenn.edu → OptionMetrics → option_price."
        )

    frames = [pd.read_csv(f, parse_dates=["date", "expiration"]) for f in files]
    df = pd.concat(frames, ignore_index=True)

    # Normalize column names
    df.columns = df.columns.str.lower().str.replace(" ", "_")
    df = df.rename(columns={
        "impl_volatility": "iv",
        "cp_flag":         "option_type",   # 'P' or 'C'
        "best_bid":        "bid",
        "best_offer":      "ask",
    })

    df["mid"]  = (df["bid"] + df["ask"]) / 2
    df["dte"]  = (df["expiration"] - df["date"]).dt.days
    df = df[
        (df["date"] >= BACKTEST_START) &
        (df["date"] <= BACKTEST_END) &
        (df["option_type"] == "P") &
        (df["dte"] > 0) &
        (df["iv"].notna()) &
        (df["iv"] > 0)
    ].copy()

    return df.sort_values("date").reset_index(drop=True)


# ── CBOE DataShop Loader ───────────────────────────────────────────────────────

def load_cboe(data_dir: str = "data/raw/cboe/") -> pd.DataFrame:
    """
    Load CBOE DataShop options data.
    Purchase from datashop.cboe.com — EOD options quotes format.
    Expected columns vary; mapped to common schema here.
    """
    path = Path(data_dir)
    files = list(path.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CBOE CSVs found in {data_dir}.")

    frames = [pd.read_csv(f, parse_dates=["quotedate", "expiration"]) for f in files]
    df = pd.concat(frames, ignore_index=True)

    df = df.rename(columns={
        "quotedate":    "date",
        "iv":           "iv",
        "type":         "option_type",
        "bid":          "bid",
        "ask":          "ask",
        "underlying":   "spot",
    })

    df["mid"] = (df["bid"] + df["ask"]) / 2
    df["dte"] = (df["expiration"] - df["date"]).dt.days
    df = df[
        (df["option_type"].str.upper() == "P") &
        (df["dte"] > 0)
    ].copy()

    return df.sort_values("date").reset_index(drop=True)


# ── Black-Scholes Simulation (no OptionMetrics required) ──────────────────────

def load_bs_simulation(
    dte_target: int = 30,
    long_strike_pct: float = 0.95,
    short_strike_pct: float = 0.90,
) -> pd.DataFrame:
    """
    Build a synthetic options history from SPY prices + VIX as IV proxy.
    No OptionMetrics access needed.

    Returns one row per trading day with both long put and spread priced.
    """
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("Run: pip install yfinance")

    spy = yf.download(UNDERLYING, start=BACKTEST_START, end=BACKTEST_END, progress=False)
    vix = yf.download("^VIX",     start=BACKTEST_START, end=BACKTEST_END, progress=False)

    spy = spy["Close"].rename("spot")
    vix = vix["Close"].rename("vix")

    df = pd.concat([spy, vix], axis=1).dropna()
    df.index.name = "date"
    df = df.reset_index()

    records = []
    for _, row in df.iterrows():
        spot = float(row["spot"])
        iv   = float(row["vix"]) / 100.0   # VIX as annualized IV proxy

        lp = price_long_put(spot, dte_target, iv, RISK_FREE_RATE, long_strike_pct)
        sp = price_put_spread(spot, dte_target, iv, RISK_FREE_RATE, long_strike_pct, short_strike_pct)

        records.append({
            "date":                row["date"],
            "spot":                spot,
            "vix":                 row["vix"],
            "iv":                  iv,
            # Long put
            "lp_strike":           lp.strike,
            "lp_premium":          lp.price,
            "lp_delta":            lp.delta,
            # Put spread
            "ps_long_strike":      sp["long_leg"].strike,
            "ps_short_strike":     sp["short_leg"].strike,
            "ps_net_debit":        sp["net_debit"],
            "ps_max_profit":       sp["max_profit"],
            "ps_breakeven":        sp["breakeven"],
        })

    return pd.DataFrame(records)


# ── Unified Entry Point ────────────────────────────────────────────────────────

def load_options_data(**kwargs) -> pd.DataFrame:
    if DATA_MODE == "optionmetrics":
        return load_optionmetrics(**kwargs)
    elif DATA_MODE == "cboe":
        return load_cboe(**kwargs)
    elif DATA_MODE == "bs_sim":
        return load_bs_simulation(**kwargs)
    else:
        raise ValueError(f"Unknown DATA_MODE: {DATA_MODE}. Choose 'bs_sim', 'optionmetrics', or 'cboe'.")
