"""One command to reproduce everything on live public data."""
import json, os
from src.experiments import run, save_figures

ROOT = os.path.dirname(os.path.dirname(__file__))
RES = os.path.join(ROOT, "results")

def main():
    res = run()
    os.makedirs(RES, exist_ok=True)
    with open(os.path.join(RES, "results.json"), "w") as f:
        json.dump(res, f, indent=2, default=str)
    save_figures(res, os.path.join(RES, "figures"))
    print(f"symbols={list(res['symbols'].keys())} trials={res['trial_count']}")
    for s, r in res["symbols"].items():
        print(f"[{s}] inv Sharpe@10={r['investigator_10bps']['sharpe']:.3f} "
              f"CAGR={r['investigator_10bps']['CAGR']:.4f} "
              f"MACD Sharpe@10={r['indicator_alone_10bps']['MACD']['sharpe']:.3f} "
              f"zones={r['E5_memory']['zones']} "
              f"real_react={r['E5_memory']['real_reaction_rate']:.3f} vs placebo={r['E5_memory']['placebo_reaction_rate']:.3f}")
    print(f"E7 mean inv Sharpe={res['E7_hidden']['mean_investigator_sharpe_10bps']:.3f} "
          f"mean MACD Sharpe={res['E7_hidden']['mean_MACD_sharpe_10bps']:.3f}")
    print("wrote results/results.json + results/figures/investigator_vs_macd.png")

if __name__ == "__main__":
    main()
