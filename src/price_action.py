"""Naked price-action reader — formalizes the Arabic course (bulls/bears tug-of-war).

Three investigator questions (no indicators, no future data):
  Q1 WHO dominates?  -> regime in {+1 up, -1 down, 0 range}  (stairs: HH/HL vs LH/LL)
  Q2 HOW strong?     -> momentum score 0..3 (body size, shallow pullback, consecutiveness)
  Q3 Is it CHANGING? -> reversal score 0..3 (new depth, failed advance, momentum flip)
                        3/3 = reversal, else tired/pullback. Never predict: describe.
Memory: support/resistance ZONES (touches>=3, width=0.25*ATR), line reveals / never decides.
All functions are past-only: row t uses rows <= t. Execution must shift by >=1 bar.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def add_candle_features(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["body"] = d["close"] - d["open"]
    d["rng"] = (d["high"] - d["low"]).replace(0, np.nan)
    d["body_abs"] = d["body"].abs()
    d["body_ratio"] = (d["body_abs"] / d["rng"]).fillna(0)
    d["upper_wick"] = d["high"] - d[["open", "close"]].max(axis=1)
    d["lower_wick"] = d[["open", "close"]].min(axis=1) - d["low"]
    d["green"] = (d["close"] > d["open"]).astype(int)
    d["atr"] = (d["high"] - d["low"]).rolling(14, min_periods=14).mean()
    d["sma50"] = d["close"].rolling(50, min_periods=50).mean()
    return d


def q1_regime(d: pd.DataFrame) -> pd.Series:
    """Stairs detector. Past-only via shift-safe rolling (current bar included, executed next bar)."""
    c = d["close"]
    hh = c.rolling(20, min_periods=20).max()
    ll = c.rolling(20, min_periods=20).min()
    prev_hh = hh.shift(20)
    prev_ll = ll.shift(20)
    up = (c > d["sma50"]) & (hh > prev_hh) & (ll > prev_ll)
    dn = (c < d["sma50"]) & (hh < prev_hh) & (ll < prev_ll)
    reg = pd.Series(0, index=d.index, dtype=int)
    reg[up.fillna(False)] = 1
    reg[dn.fillna(False)] = -1
    return reg


def q2_momentum(d: pd.DataFrame, reg: pd.Series) -> pd.Series:
    """0..3 markers: (1) winner bodies big, (2) pullbacks shallow, (3) consecutive."""
    out = pd.Series(0, index=d.index, dtype=int)
    med_body = d["body_abs"].rolling(50, min_periods=50).median()
    for i in range(len(d)):
        if i < 60:
            continue
        r = int(reg.iloc[i])
        if r == 0:
            continue
        w = d.iloc[i - 9:i + 1]
        wb = w["body"] if r == 1 else -w["body"]
        m1 = 1 if wb[wb > 0].mean() > (med_body.iloc[i] or 0) else 0
        # pullback depth vs advance over last 20
        seg = d.iloc[i - 19:i + 1]
        adv = (seg["close"].max() - seg["close"].min()) if r == 1 else (seg["close"].max() - seg["close"].min())
        # max adverse excursion from last extreme
        if r == 1:
            peak = seg["close"].cummax()
            dd = (peak - seg["close"]).max()
        else:
            trough = seg["close"].cummin()
            dd = (seg["close"] - trough).max()
        m2 = 1 if adv > 0 and dd / adv < 0.5 else 0
        aligned = (np.sign(w["body"].values) == r).sum()
        m3 = 1 if aligned >= 6 else 0
        out.iloc[i] = m1 + m2 + m3
    return out


def q3_reversal(d: pd.DataFrame, reg: pd.Series) -> pd.Series:
    """0..3 markers of dominance TRANSFER (course video 7):
    (1) new depth: pullback deeper than prior pullbacks,
    (2) failed advance: long wick / no new extreme in last 5,
    (3) momentum flip: opponent bodies bigger+consecutive last 5.
    3/3 => reversal (describe, not predict)."""
    out = pd.Series(0, index=d.index, dtype=int)
    for i in range(60, len(d)):
        r = int(reg.iloc[i])
        if r == 0:
            continue
        seg = d.iloc[i - 19:i + 1]
        cur_dd_depth = (seg["close"].cummax() - seg["close"]).max() if r == 1 else (seg["close"] - seg["close"].cummin()).max()
        prev = d.iloc[i - 39:i - 19]
        prev_dd = (prev["close"].cummax() - prev["close"]).max() if r == 1 else (prev["close"] - prev["close"].cummin()).max()
        m1 = 1 if cur_dd_depth > (prev_dd or 0) * 1.1 else 0
        last5 = d.iloc[i - 4:i + 1]
        atr = d["atr"].iloc[i] or last5["rng"].mean()
        if r == 1:
            failed = (last5["upper_wick"] > 0.4 * last5["rng"]).any() and (last5["close"].max() <= seg["close"].max())
        else:
            failed = (last5["lower_wick"] > 0.4 * last5["rng"]).any() and (last5["close"].min() >= seg["close"].min())
        m2 = 1 if failed else 0
        opp = -r
        ob = last5["body"] * opp
        m3 = 1 if (ob > 0).sum() >= 2 and ob[ob > 0].mean() > (last5["body_abs"].mean() * 0.8) and atr > 0 else 0
        out.iloc[i] = m1 + m2 + m3
    return out


def find_zones(d: pd.DataFrame, lookback: int = 120, piv: int = 3, touch_tol_atr: float = 0.25,
               min_touches: int = 3) -> list[dict]:
    """Swing-cluster memory zones from past-only pivots. Returns [{level, width, touches, kind}]."""
    zones = []
    if len(d) < lookback + 2 * piv + 5:
        return zones
    seg = d.iloc[-lookback:].reset_index(drop=True)
    atr = float(seg["atr"].iloc[-1] or seg["rng"].mean())
    pivots = []
    for i in range(piv, len(seg) - piv):
        h, l = seg["high"].iloc[i], seg["low"].iloc[i]
        if h == seg["high"].iloc[i - piv:i + piv + 1].max():
            pivots.append(("R", h, i))
        if l == seg["low"].iloc[i - piv:i + piv + 1].min():
            pivots.append(("S", l, i))
    used = set()
    for k in range(len(pivots)):
        if k in used:
            continue
        kind, lvl, _ = pivots[k]
        group = [p for j, p in enumerate(pivots) if j not in used and p[0] == kind and abs(p[1] - lvl) < atr * touch_tol_atr * 2]
        if len(group) >= min_touches:
            for j, p in enumerate(pivots):
                if p in group:
                    used.add(j)
            zones.append({"level": float(np.mean([g[1] for g in group])),
                          "width": float(atr * touch_tol_atr),
                          "touches": len(group), "kind": kind})
    return zones
