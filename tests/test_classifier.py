"""
tests/test_classifier.py

Unit tests for the regime classifier.
"""
import sys, os
sys.path.insert(0, os.path.abspath('..'))

import pytest
import pandas as pd
from src.regimes.classifier import (
    classify_vix, classify_move, classify_cor1m,
    combined_signal, classify_all
)


def test_vix_classify_calm():
    assert classify_vix(12.0) == "CALM"

def test_vix_classify_normal():
    assert classify_vix(20.0) == "NORMAL"

def test_vix_classify_elevated():
    assert classify_vix(30.0) == "ELEVATED"

def test_vix_classify_stressed():
    assert classify_vix(40.0) == "STRESSED"

def test_vix_classify_crisis():
    assert classify_vix(55.0) == "CRISIS"

def test_move_normal():
    assert classify_move(70.0) == "NORMAL"

def test_move_elevated():
    assert classify_move(100.0) == "ELEVATED"

def test_cor1m_calm():
    assert classify_cor1m(15.0) == "CALM"

def test_combined_signal_todays_regime():
    # VIX=25-35 + MOVE=90-120 → REDUCE / BUILD LIST (the dashboard's current reading)
    signal = combined_signal("ELEVATED", "ELEVATED")
    assert signal == "REDUCE / BUILD LIST"

def test_combined_crisis():
    signal = combined_signal("CRISIS", "CRISIS")
    assert signal == "EXTREME CRISIS"

def test_classify_all_returns_required_columns():
    df = pd.DataFrame({
        "vix":   [20.0, 30.0, 50.0],
        "move":  [80.0, 100.0, 170.0],
        "cor1m": [15.0, 35.0, 65.0],
    })
    result = classify_all(df)
    for col in ["vix_regime","move_regime","cor1m_regime","combined","entry_signal","exit_signal"]:
        assert col in result.columns, f"Missing column: {col}"

def test_entry_signal_fires_on_elevated():
    df = pd.DataFrame({
        "vix":   [30.0],
        "move":  [100.0],
        "cor1m": [35.0],
    })
    result = classify_all(df)
    assert result["entry_signal"].iloc[0] == True

def test_no_entry_on_normal():
    df = pd.DataFrame({
        "vix":   [20.0],
        "move":  [80.0],
        "cor1m": [15.0],
    })
    result = classify_all(df)
    assert result["entry_signal"].iloc[0] == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
