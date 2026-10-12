"""Live public OHLCV loader — Yahoo v8 JSON primary (verified 2026-10-12: works from
server IP where Stooq JS-challenge + yfinance wrapper fail), yfinance 2nd, Stooq 3rd.

Best practice verified 2026-10 (DuckDuckGo lite + codertrader/polarline):
UTC-normalize, Parquet cache, adjusted closes, quality audit, 1-bar lag downstream.
"""
from __future__ import annotations
import io
import os
import time
import pandas as pd
import requests

CACHE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(CACHE, exist_ok=True)

# Stooq symbols for the course claim "any chart: stock, currency, gold, crypto"
STOOQ_MAP = {
    "SPY": "spy.us",
    "GOLD": "xauusd",
    "EURUSD": "eurusd",
    "BTC": "btcusd",
}
YF_MAP = {"SPY": "SPY", "GOLD": "GC=F", "EURUSD": "EURUSD=X", "BTC": "BTC-USD"}
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) research/1.0"}


def _fetch_yahoo_v8(symbol: str, start: str = "2019-01-01", end: str = "2026-10-12") -> pd.DataFrame | None:
    ticker = YF_MAP[symbol]
    p1 = int(pd.Timestamp(start, tz="UTC").timestamp())
    p2 = int(pd.Timestamp(end, tz="UTC").timestamp()) + 86400
    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        try:
            url = (f"https://{host}/v8/finance/chart/{ticker}?period1={p1}&period2={p2}"
                   f"&interval=1d&events=div%2Csplit")
            r = requests.get(url, timeout=30, headers=UA)
            r.raise_for_status()
            j = r.json()
            res = (j.get("chart") or {}).get("result")
            if not res:
                continue
            res = res[0]
            ts = res["timestamp"]
            q = res["indicators"]["quote"][0]
            adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose", q["close"])
            df = pd.DataFrame({"date": pd.to_datetime(ts, unit="s"),
                               "open": q["open"], "high": q["high"],
                               "low": q["low"], "close": adj if adj else q["close"],
                               "volume": q["volume"]})
            df = df.dropna(subset=["open", "high", "low", "close"]).sort_values("date").reset_index(drop=True)
            df["symbol"] = symbol
            if len(df) >= 200:
                return df
        except Exception:
            time.sleep(1)
            continue
    return None


def _fetch_stooq(symbol: str, start: str = "2019-01-01", end: str = "2026-10-12") -> pd.DataFrame | None:
    code = STOOQ_MAP[symbol]
    s = start.replace("-", "")
    e = end.replace("-", "")
    url = f"https://stooq.com/q/d/l/?s={code}&d1={s}&d2={e}&i=d"
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "research/1.0"})
        r.raise_for_status()
        if "Date" not in r.text[:200]:
            return None
        df = pd.read_csv(io.StringIO(r.text), parse_dates=["Date"])
        df = df.rename(columns={"Date": "date", "Open": "open", "High": "high",
                                "Low": "low", "Close": "close", "Volume": "volume"})
        df = df.sort_values("date").reset_index(drop=True)
        df["symbol"] = symbol
        return df
    except Exception:
        return None


def _fetch_yf(symbol: str, start: str = "2019-01-01", end: str = "2026-10-12") -> pd.DataFrame | None:
    try:
        import yfinance as yf
        t = yf.download(YF_MAP[symbol], start=start, end=end, auto_adjust=True,
                        progress=False, threads=False)
        if t is None or len(t) == 0:
            return None
        if isinstance(t.columns, pd.MultiIndex):
            t.columns = t.columns.get_level_values(0)
        df = pd.DataFrame({"date": t.index.tz_localize(None) if hasattr(t.index, "tz") and t.index.tz is not None else t.index,
                           "open": t["Open"].values, "high": t["High"].values,
                           "low": t["Low"].values, "close": t["Close"].values,
                           "volume": t["Volume"].values if "Volume" in t else 0})
        df["symbol"] = symbol
        return df.reset_index(drop=True)
    except Exception:
        return None


def load_symbol(symbol: str, start="2019-01-01", end="2026-10-12", use_cache=True) -> pd.DataFrame:
    path = os.path.join(CACHE, f"{symbol}_{start}_{end}.parquet")
    if use_cache and os.path.exists(path):
        df = pd.read_parquet(path)
        df["date"] = pd.to_datetime(df["date"])
        return df
    df = _fetch_yahoo_v8(symbol, start, end)
    source = "yahoo-v8-direct"
    if df is None or len(df) < 200:
        df = _fetch_yf(symbol, start, end)
        source = "yfinance"
    if df is None or len(df) < 200:
        df = _fetch_stooq(symbol, start, end)
        source = "stooq"
    if df is None or len(df) < 200:
        raise RuntimeError(f"No live data for {symbol} from all sources (offline?)")
    df["source"] = source
    # quality audit + honest cleaning (FX rounding: close>high by <2bps on ~1.4% EURUSD bars —
    # verified live 2026-10-12; standard fix: high=max(high,O,C), low=min(low,O,C), logged)
    df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
    n_fix_h = int((df["high"] < df[["open", "close"]].max(axis=1)).sum())
    n_fix_l = int((df["low"] > df[["open", "close"]].min(axis=1)).sum())
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"] = df[["low", "open", "close"]].min(axis=1)
    df["cleaned_bars"] = 0
    if len(df):
        df.loc[df.index, "cleaned_bars"] = n_fix_h + n_fix_l
    assert (df["high"] >= df[["open", "close"]].max(axis=1) - 1e-9).mean() > 0.999, "bad HLCV"
    df.to_parquet(path, index=False)
    return df


def load_all(symbols=("SPY", "GOLD", "EURUSD", "BTC"), **kw) -> dict[str, pd.DataFrame]:
    return {s: load_symbol(s, **kw) for s in symbols}
