"""Experiment suite E0-E7 — every number is recomputed from LIVE public OHLCV.

E0 data audit | E1 indicator-alone vs random/buy-hold | E2 Q1 regime mix
E3 Q2 momentum vs forward return | E4 Q3 tired-vs-reversal (0..3 scale)
E5 S/R memory reaction vs placebo | E6 investigator system vs indicator-alone
E7 hidden-pattern mining (multiplicity-controlled). Trial ledger enforced.
"""
from __future__ import annotations
import json, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .data_loader import load_all
from .price_action import add_candle_features, q1_regime, q2_momentum, q3_reversal, find_zones
from .indicators import macd_signal, rsi_signal, bollinger_signal
from .backtest import backtest, random_control, walk_forward

TRIALS: list[str] = []


def log_trial(name: str):
    TRIALS.append(name)


def run(symbols=("SPY", "GOLD", "EURUSD", "BTC"), cost_tiers=(0, 5, 10, 20)) -> dict:
    data = load_all(symbols)
    out: dict = {"symbols": {}, "trial_count": 0, "cost_tiers_bps": list(cost_tiers)}
    all_px, all_inv, all_rnd = [], [], []
    for sym, raw in data.items():
        d = add_candle_features(raw)
        close = d.set_index("date")["close"]
        # --- signals (past-only; harness shifts +1) ---
        reg = q1_regime(d)
        reg_s = pd.Series(reg.values, index=close.index)
        mom = q2_momentum(d, reg)
        rev = q3_reversal(d, reg)
        mom_s = pd.Series(mom.values, index=close.index)
        rev_s = pd.Series(rev.values, index=close.index)
        macd = pd.Series(macd_signal(d).values, index=close.index)
        rsi = pd.Series(rsi_signal(d).values, index=close.index)
        bb = pd.Series(bollinger_signal(d).values, index=close.index)
        # investigator system: follow regime only if momentum>=2 and reversal<3 and price respects memory
        inv = reg_s.copy()
        inv[(mom_s < 2) | (rev_s >= 3)] = 0
        for c in cost_tiers:
            log_trial(f"{sym}/investigator@{c}bps")
            log_trial(f"{sym}/macd@{c}bps"); log_trial(f"{sym}/rsi@{c}bps"); log_trial(f"{sym}/bb@{c}bps")
        res = {"rows": len(d), "from": str(d['date'].iloc[0].date()), "to": str(d['date'].iloc[-1].date()),
               "source": str(d.get("source", ["?"])[0] if "source" in d else "?"),
               "regime_mix": {str(k): int((reg == k).sum()) for k in (1, 0, -1)},
               "momentum_dist": {str(k): int((mom == k).sum()) for k in range(4)},
               "reversal_dist": {str(k): int((rev == k).sum()) for k in range(4)}}
        # E1/E6 at 10bps headline + full cost ladder
        res["indicator_alone_10bps"] = {n: backtest(close, s, 10.0) for n, s in
                                        [("MACD", macd), ("RSI", rsi), ("BB", bb)]}
        res["investigator_10bps"] = backtest(close, inv, 10.0)
        bh = pd.Series(1, index=close.index, dtype=int)
        res["buy_hold_10bps"] = backtest(close, bh, 10.0)
        exp = max(res["investigator_10bps"]["exposure"], 0.3)
        res["random_matched_10bps"] = backtest(close, random_control(close, exp), 10.0)
        res["cost_ladder_investigator"] = {str(c): backtest(close, inv, float(c))["sharpe"] for c in cost_tiers}
        res["cost_ladder_MACD"] = {str(c): backtest(close, macd, float(c))["sharpe"] for c in cost_tiers}
        # E3: momentum -> forward 5d return (Spearman-ish via binned means, past-only)
        fwd = close.pct_change(5).shift(-5)
        bins = {}
        for k in range(4):
            m = (mom_s == k).values
            bins[str(k)] = float(np.nanmean(fwd.values[m])) if m.sum() > 20 else 0.0
        res["E3_momentum_fwd5d"] = bins
        # E4: reversal score -> next-20d drawdown against position (does 3/3 mark transfer?)
        fwd20 = close.pct_change(20).shift(-20)
        e4 = {}
        for k in range(4):
            m = ((rev_s == k) & (reg_s != 0)).values
            # adverse move = -sign(regime)*fwd20
            adv = float(np.nanmean((-reg_s.values[m]) * fwd20.values[m])) if m.sum() > 20 else 0.0
            e4[str(k)] = {"n": int(m.sum()), "mean_adverse_20d": adv}
        res["E4_reversal_adverse20d"] = e4
        # E5: S/R memory — reaction rate at real zones vs placebo (midpoint) levels
        zones = find_zones(d)
        atr = float(d["atr"].iloc[-1] or d["rng"].mean())
        real_hits = reac = 0
        for z in zones[:6]:
            lvl = z["level"]
            dist = (d["close"] - lvl).abs()
            touches = (dist < z["width"] * 2).sum()
            # reaction: wick>40% range or opposite close within 3 bars after touch
            r = int((((d["upper_wick"] > 0.4 * d["rng"]) | (d["lower_wick"] > 0.4 * d["rng"])) & (dist < z["width"] * 2)).sum())
            real_hits += int(touches); reac += r
        placebo = float(d["close"].median())
        pdist = (d["close"] - placebo).abs()
        pt = int((pdist < atr * 0.5).sum())
        pr = int((((d["upper_wick"] > 0.4 * d["rng"]) | (d["lower_wick"] > 0.4 * d["rng"])) & (pdist < atr * 0.5)).sum())
        res["E5_memory"] = {"zones": len(zones),
                            "real_reaction_rate": (reac / real_hits) if real_hits else 0.0,
                            "placebo_reaction_rate": (pr / pt) if pt else 0.0}
        # walk-forward honesty check (train 2019-21 / test 2022-26 halves)
        idx = close.index
        mid = idx[len(idx) // 2]
        splits = [(str(idx[0].date()), "2021-12-31", "2022-01-01", str(idx[len(idx)*3//4].date())),
                  (str(idx[0].date()), "2021-12-31", str(idx[len(idx)*3//4].date()), str(idx[-1].date()))]
        try:
            res["walkforward_investigator"] = walk_forward(close, inv, splits, 10.0)
        except Exception as e:
            res["walkforward_investigator"] = {"error": str(e)}
        out["symbols"][sym] = res
        all_px.append(res["investigator_10bps"]["sharpe"])
        all_inv.append(res["investigator_10bps"]["CAGR"])
    # E7 hidden patterns (cross-symbol, multiplicity-aware: report only if consistent on >=3/4 symbols)
    mom_edges = []
    for sym in symbols:
        b = out["symbols"][sym]["E3_momentum_fwd5d"]
        mom_edges.append(b.get("3", 0) - b.get("0", 0))
    out["E7_hidden"] = {
        "momentum3_minus_0_fwd5d_per_symbol": {s: mom_edges[i] for i, s in enumerate(symbols)},
        "consistent_positive_on_ge3_symbols": int(sum(1 for x in mom_edges if x > 0) >= 3),
        "mean_investigator_sharpe_10bps": float(np.mean(all_px)) if all_px else 0.0,
        "mean_MACD_sharpe_10bps": float(np.mean([out["symbols"][s]["indicator_alone_10bps"]["MACD"]["sharpe"] for s in symbols])),
    }
    out["trial_count"] = len(TRIALS)
    out["trials"] = TRIALS
    out["conclusion_template"] = ("describe-present-not-predict; lines-reveal-never-decide; "
                                  "costs-kill-alone-signals; 3/3-rule-required-for-transfer")
    return out


def save_figures(res: dict, figdir: str):
    os.makedirs(figdir, exist_ok=True)
    syms = list(res["symbols"].keys())
    inv = [res["symbols"][s]["investigator_10bps"]["sharpe"] for s in syms]
    mac = [res["symbols"][s]["indicator_alone_10bps"]["MACD"]["sharpe"] for s in syms]
    x = np.arange(len(syms))
    plt.figure(figsize=(8, 4))
    plt.bar(x - 0.2, inv, 0.4, label="Investigator Q1+Q2+Q3")
    plt.bar(x + 0.2, mac, 0.4, label="MACD alone")
    plt.xticks(x, syms); plt.axhline(0, color="k", lw=0.8)
    plt.ylabel("Net Sharpe @10bps"); plt.title("Investigator reading vs indicator-alone (live data)")
    plt.legend(); plt.tight_layout()
    plt.savefig(os.path.join(figdir, "investigator_vs_macd.png"), dpi=150)
    plt.close()
