# PAPER DRAFT — The Price-Action Investigator (v1.0, 2026-10-12)

Full publishable text lives in `README.md` (§0–§13). This file is the submission-ready wrapper.

**Title:** Naked Reading vs Indicator-Chasing: A Pre-Committed Live-Data Verification of a Price-Action Curriculum Across Equities, Gold, FX and Crypto (2019–2026)

**Authors:** Independent verification lab — contact via repo issues.

**Abstract:** see README §0. Key numbers: n=4 markets, 1,955–2,842 bars each, 64 logged trials, 1-bar lag, 0–20 bps ladder, walk-forward OOS. Indicator-alone mean Sharpe −0.30 @10bps; investigator reading −0.15; momentum-3 minus momentum-0 forward-5d +14–39 bps on 4/4 symbols; S/R reaction ≈ placebo; costs erase both families.

**Formal operators (for reviewers):**
- Q1: `UP_t = 1[C_t>SMA50_t ∧ HH20_t>HH20_{t-20} ∧ LL20_t>LL20_{t-20}]`, DN mirrored, else RANGE.
- Q2: `M = m1+m2+m3`, m1: winner-body>median50, m2: DD20/ADV20<0.5, m3: ≥6/10 aligned.
- Q3: `R = r1+r2+r3`, r1: DD20>1.1·DDprior20, r2: wick>0.4·range in last-5 ∧ no new extreme, r3: opponent decisive last-5. Transfer-described iff R=3.
- Memory: pivots(p=3) clustered <0.5·ATR, width 0.25·ATR, touches≥3. Reveal-only.
- Harness: `pos_t = sig_{t-1}`, `r_net = pos·r − |Δpos|·bps/1e4`. Metrics: CAGR/vol/Sharpe/Sortino/maxDD/Calmar/win/PF/exposure/trades.
- Multiplicity: fixed mappings (0 df search), 64-trial ledger, ≥3/4-symbol consistency rule, |t|≥3/BY-FDR qualitative bar; formal DSR `DSR = Φ[(ŜR−SR0)√(T−1)/√(1−γ3ŜR+(γ4−1)ŜR²/4)]` deferred to Ch.2 with trial count T=64.

**Reproduction:** `docker compose up research` → `results/results.json` + `results/figures/investigator_vs_macd.png`. Live pull 2026-10-12 cached to `data/*.parquet` (delete to re-pull). Tests: `python -m pytest tests/ -q` (lag + cost-monotonicity).

**Ethics:** education only; no advice; no profit promise; costs/slippage/borrow understated for shorts — reported net is optimistic for shorts.

**Status:** v1.0 verified. Next: intraday/weekly invariance, zone-break conjunction rare-event model, DSR/PBO formal, execution-overlay chapter.
