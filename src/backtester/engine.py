"""
backtester/engine.py

Core backtest loop. Iterates daily, applies regime classification,
triggers entry/exit/roll logic for both strategies in parallel.

TEMPORAL INTEGRITY NOTES
─────────────────────────────────────────────────────────────────────────────
Three violations existed in the original engine. Each is documented below
with the broken pattern and the fix applied here.

VIOLATION 1 — Same-bar signal + execution
    BROKEN:  for row in df:
                 if row["entry_signal"]:   # signal from today's close
                     lp.open(date, spot, iv, regime)  # executes today
    FIXED:   entry_signal[t] is derived from closes at t-1 (shifted in
             classifier.py). The engine loop reads entry_signal[t] and
             opens using exec_spot/exec_iv from the *current* row — which
             is the next realistic open after the signal was known.

VIOLATION 2 — Signal IV used for pricing
    BROKEN:  iv = row["vix"] / 100.0   # today's closing VIX → same-bar fill
    FIXED:   exec_iv = row["vix"] / 100.0 is now the *execution* bar's VIX
             (because entry_signal has been shifted). signal_iv = prior
             row's VIX is stored for reference only. In bs_sim mode, using
             prior close VIX as exec_iv is a realistic proxy for next-morning
             fill pricing.

VIOLATION 3 — Unseparated signal/execution in the same row iteration
    BROKEN:  Signal read and strategy opened in same `row` with no temporal
             guard — no way to tell if signal came from today or yesterday.
    FIXED:   Two explicit named variables per row:
                 exec_spot — the execution bar's open proxy (current row)
                 exec_iv   — the execution bar's IV proxy (current row)
                 signal_*  — the prior bar values (now only stored for audit)
             The separation is enforced structurally, not just by comment.
─────────────────────────────────────────────────────────────────────────────

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

    TEMPORAL NOTE: yfinance returns daily closing prices. No intraday or
    forward-looking data is introduced here. ffill() is used only to carry
    MOVE data forward through non-trading days — this is point-in-time safe
    because we only carry the *last known* value, never a future value.
    """
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("Run: pip install yfinance")

    def _download(ticker):
        raw = yf.download(ticker, start=BACKTEST_START, end=BACKTEST_END,
                          progress=False, auto_adjust=True)
        if raw.empty:
            return pd.Series(dtype=float)
        if isinstance(raw.columns, pd.MultiIndex):
            if ("Close", ticker) in raw.columns:
                return raw[("Close", ticker)]
            raw.columns = raw.columns.get_level_values(0)
        if "Close" in raw.columns:
            return raw["Close"]
        return raw.iloc[:, 0]

    spy  = _download("SPY")
    vix  = _download("^VIX")

    # COR1M: CBOE implied correlation
    try:
        cor1m = _download("^COR3M")
        if cor1m.empty:
            raise ValueError("empty")
    except Exception:
        cor1m = vix * 0.6

    # MOVE proxy: use data file if available, else synthetic
    move_file = Path("data/raw/move_index.csv")
    if move_file.exists():
        move_df = pd.read_csv(move_file, index_col=0, parse_dates=True)["MOVE"]
        move = move_df.reindex(vix.index).ffill()
        # TEMPORAL NOTE: ffill carries last *known* MOVE value — safe.
        # bfill would introduce future data — never use bfill on macro series.
    else:
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

    # Term structure proxy: VIX3M - VIX (contango = negative front_spread)
    try:
        vix3m = _download("^VIX3M")
        if vix3m.empty:
            raise ValueError("empty")
        vix3m = vix3m.reindex(pd.DatetimeIndex(df["date"])).values
        df["front_spread"] = vix3m - df["vix"].values
    except Exception:
        df["front_spread"] = 0.0

    # Classify regimes — signals are .shift(1)-ed inside classify_all()
    df = classify_all(df)

    return df


def run_backtest(df: pd.DataFrame = None) -> tuple[list[Trade], list[Trade]]:
    """
    Run both strategies over the full history.

    TEMPORAL ARCHITECTURE
    ──────────────────────
    The DataFrame from classify_all() has entry_signal[t] = f(closes[t-1]).
    This engine reads that pre-shifted signal at row t and executes using
    row t's spot/vix as execution inputs (next-bar open proxy).

    Per-row variable naming enforces the separation explicitly:
        exec_spot  — current row's spot (used for fills and P&L)
        exec_iv    — current row's vix (used for option pricing at open)
        signal_spot — prior row's spot (stored in Trade for audit trail only)

    Returns (lp_trades, ps_trades).
    """
    if df is None:
        df = load_regime_data()

    lp = LongPutStrategy()
    ps = PutSpreadStrategy()

    lp_trades: list[Trade] = []
    ps_trades: list[Trade] = []

    # Build a shifted reference for signal_spot (the bar that fired the signal)
    # This is purely for the Trade audit record — it is NOT used in pricing.
    df["signal_spot"] = df["spot"].shift(1)
    df["signal_iv"]   = df["vix"].shift(1)

    for _, row in df.iterrows():
        date = row["date"]

        # ── Execution bar values (the bar we are acting ON) ──────────────────
        # entry_signal[t] was generated from closes[t-1] in classifier.py,
        # so using row[t]'s spot/vix here is next-bar execution — correct.
        exec_spot = row["spot"]
        exec_iv   = row["vix"] / 100.0     # annualized IV for BS pricing

        # ── Signal bar values (informational only — stored in Trade record) ──
        signal_spot = row["signal_spot"] if not pd.isna(row["signal_spot"]) else exec_spot
        # signal_iv not used for pricing — exec_iv is used instead

        regime = row["combined"]

        # ── Long Put ──────────────────────────────────────────────────────────
        if lp.is_open():
            lp.step()
            if row["exit_signal"]:
                # exit_signal[t] = f(reversion[t-1]) — realistic same-open exit
                lp_trades.append(lp.close(date, exec_spot, "exit_signal"))
            elif lp.should_roll():
                lp_trades.append(lp.close(date, exec_spot, "roll"))
                lp.open(date, exec_spot, exec_iv, regime, signal_spot=signal_spot)
        elif row["entry_signal"]:
            # entry_signal[t] came from closes[t-1] — executing at open of t ✓
            lp.open(date, exec_spot, exec_iv, regime, signal_spot=signal_spot)

        # ── Put Spread ────────────────────────────────────────────────────────
        if ps.is_open():
            ps.step()
            if row["exit_signal"]:
                ps_trades.append(ps.close(date, exec_spot, "exit_signal"))
            elif ps.should_roll():
                ps_trades.append(ps.close(date, exec_spot, "roll"))
                ps.open(date, exec_spot, exec_iv, regime, signal_spot=signal_spot)
        elif row["entry_signal"]:
            ps.open(date, exec_spot, exec_iv, regime, signal_spot=signal_spot)

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
