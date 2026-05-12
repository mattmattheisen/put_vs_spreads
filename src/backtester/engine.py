"""
backtester/engine.py

Core backtest loop. Iterates daily, applies regime classification,
triggers entry/exit/roll logic for both strategies in parallel.

Usage:
    python -m src.backtester.engine
"""

import pandas as pd
import numpy as np
from pathlib import Path
from config import BACKTEST_START, BACKTEST_END, RESULTS_DIR
from src.options.loader import load_options_data
from src.regimes.classifier import classify_all
from src.backtester.strategies import LongPutStrategy, PutSpreadStrategy, Trade
from src.backtester.metrics import compute_metrics, print_summary


def load_regime_data() -> pd.DataFrame:
    """
    Load daily VIX, MOVE, COR1M data and classify regimes.
    In bs_sim mode, MOVE and COR1M are pulled from yfinance proxies.
    CBOE COR1M ticker: ^COR1M (may need Bloomberg/Refinitiv for full history)
    MOVE proxy: can use ICE BofA MOVE via FRED (BAMLEMHBHYCRPIOAS as rough proxy)
    """
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("Run: pip install yfinance")

    spy = yf.download("SPY",  start=BACKTEST_START, end=BACKTEST_END, progress=False)["Close"]
    vix = yf.download("^VIX", start=BACKTEST_START, end=BACKTEST_END, progress=False)["Close"]

    # COR1M: CBOE implied correlation — use ^COR3M as available proxy
    try:
        cor1m = yf.download("^COR3M", start=BACKTEST_START, end=BACKTEST_END, progress=False)["Close"]
    except Exception:
        # Fallback: synthetic correlation proxy from VIX / realized vol ratio
        cor1m = vix * 0.6  # rough proxy; replace with real COR1M data

    # MOVE proxy: use FRED BAMLH0A0HYM2 or manual data file if available
    move_file = Path("data/raw/move_index.csv")
    if move_file.exists():
        move_df = pd.read_csv(move_file, index_col=0, parse_dates=True)["MOVE"]
        move = move_df.reindex(vix.index).ffill()
    else:
        # Synthetic proxy: MOVE ≈ 3.5x VIX historically (rough)
        move = vix * 3.5
        print("[WARNING] No MOVE data file found. Using VIX×3.5 as proxy.")
        print("         Download real MOVE data from FRED (BAMLHYH0A0HYM2EY) or Bloomberg.")

    df = pd.DataFrame({
        "spot":  spy,
        "vix":   vix,
        "move":  move,
        "cor1m": cor1m,
    }).dropna()

    df.index.name = "date"
    df = df.reset_index()

    # Add term structure proxy: VIX3M - VIX (contango/backwardation)
    try:
        vix3m = yf.download("^VIX3M", start=BACKTEST_START, end=BACKTEST_END, progress=False)["Close"]
        vix3m = vix3m.reindex(pd.DatetimeIndex(df["date"])).values
        df["front_spread"] = vix3m - df["vix"].values
    except Exception:
        df["front_spread"] = 0.0

    # Classify regimes
    df = classify_all(df)

    return df


def run_backtest(df: pd.DataFrame = None) -> tuple[list[Trade], list[Trade]]:
    """
    Run both strategies over the full history.
    Returns (lp_trades, ps_trades).
    """
    if df is None:
        df = load_regime_data()

    lp = LongPutStrategy()
    ps = PutSpreadStrategy()

    lp_trades: list[Trade] = []
    ps_trades: list[Trade] = []

    for _, row in df.iterrows():
        date  = row["date"]
        spot  = row["spot"]
        iv    = row["vix"] / 100.0   # annualized IV
        regime = row["combined"]

        # ── Long Put ──────────────────────────────────────────────────────────
        if lp.is_open():
            lp.step()
            if row["exit_signal"]:
                lp_trades.append(lp.close(date, spot, "exit_signal"))
            elif lp.should_roll():
                lp_trades.append(lp.close(date, spot, "roll"))
                lp.open(date, spot, iv, regime)
        elif row["entry_signal"]:
            lp.open(date, spot, iv, regime)

        # ── Put Spread ────────────────────────────────────────────────────────
        if ps.is_open():
            ps.step()
            if row["exit_signal"]:
                ps_trades.append(ps.close(date, spot, "exit_signal"))
            elif ps.should_roll():
                ps_trades.append(ps.close(date, spot, "roll"))
                ps.open(date, spot, iv, regime)
        elif row["entry_signal"]:
            ps.open(date, spot, iv, regime)

    # Close any open positions at end of sample
    if lp.is_open():
        last = df.iloc[-1]
        lp_trades.append(lp.close(last["date"], last["spot"], "end_of_sample"))
    if ps.is_open():
        last = df.iloc[-1]
        ps_trades.append(ps.close(last["date"], last["spot"], "end_of_sample"))

    return lp_trades, ps_trades


def trades_to_df(trades: list[Trade]) -> pd.DataFrame:
    return pd.DataFrame([t.__dict__ for t in trades])


if __name__ == "__main__":
    print("Loading regime data...")
    regime_df = load_regime_data()

    print(f"Running backtest: {BACKTEST_START} → {BACKTEST_END}")
    lp_trades, ps_trades = run_backtest(regime_df)

    lp_df = trades_to_df(lp_trades)
    ps_df = trades_to_df(ps_trades)

    Path(RESULTS_DIR).mkdir(exist_ok=True)
    lp_df.to_csv(f"{RESULTS_DIR}long_put_trades.csv", index=False)
    ps_df.to_csv(f"{RESULTS_DIR}put_spread_trades.csv", index=False)

    print("\n── Long Put ──────────────────────────────")
    print_summary(lp_df)
    print("\n── Put Spread ────────────────────────────")
    print_summary(ps_df)
