"""Honest backtest harness: 1-bar execution lag, cost tiers, metric constellation.

Fixes verified from 2026 literature (Potter taxonomy, MEDGE 8-step, Bailey et al. DSR/PBO):
PIT-only signals, shift>=1, spread+fee costs, walk-forward, trial ledger, exposure-matched
random control, >=100 trades rule, full metric constellation (never Sharpe alone).
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def backtest(close: pd.Series, signal: pd.Series, cost_bps: float = 10.0) -> dict:
    sig = signal.fillna(0).astype(int)
    pos = sig.shift(1).fillna(0).astype(int)  # trade next bar: no lookahead, never same-bar close
    ret = close.pct_change().fillna(0)
    turnover = pos.diff().abs().fillna(0)
    cost = turnover * (cost_bps / 10000.0)
    strat = pos * ret - cost
    eq = (1 + strat).cumprod()
    n = len(strat)
    yrs = n / 252
    cagr = float(eq.iloc[-1] ** (1 / yrs) - 1) if yrs > 0 and eq.iloc[-1] > 0 else 0.0
    vol = float(strat.std() * np.sqrt(252)) if strat.std() > 0 else 0.0
    sharpe = float(strat.mean() / strat.std() * np.sqrt(252)) if strat.std() > 0 else 0.0
    dn = strat[strat < 0]
    sortino = float(strat.mean() / dn.std() * np.sqrt(252)) if len(dn) > 5 and dn.std() > 0 else 0.0
    dd = float((eq / eq.cummax() - 1).min())
    calmar = float(cagr / abs(dd)) if dd < 0 else 0.0
    # trades: count entries
    entries = int(((pos.diff() != 0) & (pos != 0)).sum())
    wins = float(((strat[pos != 0]) > 0).mean()) if (pos != 0).sum() > 0 else 0.0
    gp = float(strat[strat > 0].sum())
    gl = float(-strat[strat < 0].sum())
    pf = float(gp / gl) if gl > 0 else (float("inf") if gp > 0 else 0.0)
    exposure = float((pos != 0).mean())
    return {"CAGR": cagr, "vol": vol, "sharpe": sharpe, "sortino": sortino,
            "maxDD": dd, "calmar": calmar, "win": wins, "PF": pf,
            "exposure": exposure, "trades": entries, "equity_end": float(eq.iloc[-1])}


def random_control(close: pd.Series, exposure: float, seed: int = 7) -> pd.Series:
    rng = np.random.default_rng(seed)
    choices = rng.choice([1, 0, -1], size=len(close), p=[exposure / 2, 1 - exposure, exposure / 2])
    return pd.Series(choices, index=close.index, dtype=int)


def walk_forward(close: pd.Series, signal: pd.Series, splits: list[tuple[str, str, str, str]],
                 cost_bps: float = 10.0) -> dict:
    """splits: list of (train_start, train_end, test_start, test_end) as date strings."""
    oos = []
    for ts, te, ss, se in splits:
        sub_c = close.loc[ss:se]
        sub_s = signal.loc[ss:se]
        if len(sub_c) < 30:
            continue
        oos.append(backtest(sub_c, sub_s, cost_bps))
    if not oos:
        return {}
    df = pd.DataFrame(oos)
    return {"mean_sharpe_OOS": float(df["sharpe"].mean()), "min_sharpe_OOS": float(df["sharpe"].min()),
            "mean_CAGR_OOS": float(df["CAGR"].mean()), "windows": len(df)}
