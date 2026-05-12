spread-or-bleed — Long Puts vs. Put Spreads
Regime-conditioned options strategy comparison using VIX, MOVE, and COR1M signals.
---
Hypothesis
> **Do long puts outperform put spreads as tail protection — and does the answer change by volatility regime?**
This repo tests whether the optimal hedging structure (outright long put vs. put spread) is regime-dependent, using the MMS Vol Dashboard signals as entry/exit filters.
---
Regime Framework
Signals derived from the VIX × MOVE × COR1M Combined Signal Matrix:
Regime	VIX	MOVE	COR1M	Signal
CALM	<15	<90	<20	Full deployment
NORMAL	15–25	<90	20–40	Standard ops
ELEVATED	25–35	90–120	40–60	Reduce / build list
STRESSED	35–45	120–160	>40	Quality only
CRISIS	>45	>160	>60	Max cash
Entry triggered when regime shifts into ELEVATED or higher. Exit on reversion (6-of-6 pivot conditions met).
---
Strategy Definitions
Long Put
Buy ATM or 5% OTM put on SPX/SPY
30-DTE rolling
Full premium at risk
Put Spread (Bear Put Spread)
Buy ATM or 5% OTM put, sell 10% OTM put
Same 30-DTE rolling
Capped profit, reduced cost
Comparison Metrics
P&L (realized at expiry or roll)
Cost per hedge (net premium paid)
Max drawdown protection (% SPX decline captured)
Breakeven move required
Win rate by regime
Sharpe of the hedge leg
---
Data Requirements
Data	Source	Notes
SPX daily OHLCV	CBOE / Yahoo Finance	Free via `yfinance`
VIX daily	CBOE	Free via `yfinance` (^VIX)
MOVE Index	CBOE / Bloomberg	ICE BAML MOVE via Bloomberg or Quandl
COR1M	CBOE	CBOE Implied Correlation Index
Options chain (historical)	OptionMetrics / CBOE DataShop	Required for realistic fill pricing
> **Note:** Without OptionMetrics access, the backtester defaults to Black-Scholes simulation using realized VIX as IV proxy. Set `DATA_MODE = "bs_sim"` in `config.py`.
---
Project Structure
```
gambit_vol_backtest/
├── data/                        # Raw + processed data (gitignored)
│   ├── raw/                     # OptionMetrics exports, CBOE downloads
│   └── processed/               # Cleaned daily regime logs
├── src/
│   ├── regimes/
│   │   ├── classifier.py        # VIX × MOVE × COR1M regime classification
│   │   └── signals.py           # Entry/exit signal generation
│   ├── options/
│   │   ├── pricing.py           # Black-Scholes pricer (sim fallback)
│   │   └── loader.py            # OptionMetrics data loader
│   └── backtester/
│       ├── engine.py            # Core backtest loop
│       ├── strategies.py        # LongPut + PutSpread strategy classes
│       └── metrics.py           # Performance analytics
├── notebooks/
│   └── 01_regime_vs_strategy.ipynb   # Main analysis notebook
├── tests/
│   ├── test_classifier.py
│   ├── test_pricing.py
│   └── test_engine.py
├── results/                     # Output charts + CSVs (gitignored)
├── config.py                    # All parameters in one place
├── requirements.txt
└── README.md
```
---
Quick Start
```bash
# Clone and install
git clone https://github.com/your-org/gambit_vol_backtest.git
cd gambit_vol_backtest
pip install -r requirements.txt

# Configure data mode
# Edit config.py: DATA_MODE = "bs_sim"  (no OptionMetrics)
#              or DATA_MODE = "optionmetrics"  (with OM access)

# Run the backtest
python -m src.backtester.engine

# Open the analysis notebook
jupyter lab notebooks/01_regime_vs_strategy.ipynb
```
---
Configuration (`config.py`)
```python
DATA_MODE       = "bs_sim"       # "bs_sim" | "optionmetrics"
BACKTEST_START  = "2018-01-01"
BACKTEST_END    = "2024-12-31"
UNDERLYING      = "SPY"
DTE_TARGET      = 30             # Days to expiry
PUT_STRIKE_PCT  = 0.95           # 5% OTM long put
SHORT_STRIKE_PCT= 0.90           # 10% OTM short put (spread only)
ROLL_DTE        = 7              # Roll when < 7 DTE
POSITION_SIZE   = 1              # Number of contracts
```
---
Key Questions
Which structure is cheaper per unit of protection? Regime-bucketed cost comparison.
When does the spread cap hurt you most? Identifies which crisis events exceeded the short strike.
Does the reversion signal (6-of-6 conditions) time exits well? PnL at signal vs. expiry.
What's the cost drag on a fully-hedged portfolio? Annual premium spend by regime.
---
Presentation Outputs
The notebook generates:
Regime timeline heatmap (VIX + MOVE + COR1M)
P&L curves: Long Put vs. Put Spread by regime
Cost-per-hedge bar chart (annualized by regime)
Tail capture efficiency scatter
Key stats summary table
---
