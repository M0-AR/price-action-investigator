"""Indicator-alone baselines (from scratch, no TA-Lib) — the 'closed device' from video 1."""
from __future__ import annotations
import pandas as pd


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def macd_signal(df: pd.DataFrame) -> pd.Series:
    m = ema(df["close"], 12) - ema(df["close"], 26)
    sig = ema(m, 9)
    out = pd.Series(0, index=df.index, dtype=int)
    out[m > sig] = 1
    out[m < sig] = -1
    return out


def rsi_signal(df: pd.DataFrame, n: int = 14) -> pd.Series:
    d = df["close"].diff()
    up = d.clip(lower=0).rolling(n, min_periods=n).mean()
    dn = (-d.clip(upper=0)).rolling(n, min_periods=n).mean()
    rs = up / dn.replace(0, float("nan"))
    rsi = 100 - 100 / (1 + rs)
    out = pd.Series(0, index=df.index, dtype=int)
    out[rsi < 30] = 1
    out[rsi > 70] = -1
    return out.fillna(0).astype(int)


def bollinger_signal(df: pd.DataFrame, n: int = 20, k: float = 2.0) -> pd.Series:
    ma = df["close"].rolling(n, min_periods=n).mean()
    sd = df["close"].rolling(n, min_periods=n).std()
    out = pd.Series(0, index=df.index, dtype=int)
    out[df["close"] < ma - k * sd] = 1
    out[df["close"] > ma + k * sd] = -1
    return out.fillna(0).astype(int)
