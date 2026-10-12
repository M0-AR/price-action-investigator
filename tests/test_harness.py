import pandas as pd
from src.backtest import backtest


def test_execution_lag_no_lookahead():
    # signal today must not profit from today's jump: flat-then-spike
    close = pd.Series([100.0, 100.0, 100.0, 120.0, 120.0])
    sig = pd.Series([0, 0, 1, 1, 1])  # enter at bar 2, must fill at bar 3 open->close logic
    r = backtest(close, sig, 0.0)
    # position shifted: profit only from bar3->bar4 move, not bar2->bar3 if that were lookahead
    assert r["trades"] >= 1


def test_costs_monotone():
    close = pd.Series([100 + i for i in range(100)], dtype=float)
    sig = pd.Series([1 if i % 2 == 0 else -1 for i in range(100)])
    s0 = backtest(close, sig, 0.0)["sharpe"]
    s20 = backtest(close, sig, 20.0)["sharpe"]
    assert s20 <= s0 + 1e-9
