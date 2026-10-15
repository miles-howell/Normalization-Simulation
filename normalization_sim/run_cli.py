
import os
import argparse
import numpy as np
import pandas as pd
from .sim import Params, Simulation
from .plots import plot_metrics, animate_agents

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--N", type=int, default=240)
    ap.add_argument("--days", type=int, default=150)
    ap.add_argument("--lambda_", type=float, default=0.15)
    ap.add_argument("--engagement", type=int, default=0, help="0=normalize to mean, 1=amplify extremes")
    ap.add_argument("--minority_share", type=float, default=0.3)
    ap.add_argument("--base_majority", type=float, default=1.0)
    ap.add_argument("--base_minority", type=float, default=0.5)
    ap.add_argument("--survival_floor", type=float, default=0.5)
    ap.add_argument("--p_edge", type=float, default=0.06)
    ap.add_argument("--shock_sd", type=float, default=0.25, help="daily resource shock (lognormal sd); 0=none")
    ap.add_argument("--homophily", type=float, default=2.0, help="preference for like-minded partners")
    ap.add_argument("--opinion_altruism", type=float, default=1.0, help="how much opinion distance cuts giving")
    ap.add_argument("--opinion_trust", type=float, default=0.03, help="trust loss per unit opinion distance")
    ap.add_argument("--extremity_susceptibility", type=float, default=0.8, help="0..1; how much distance from the mean drives outlier recruitment")
    ap.add_argument("--trust_half", type=float, default=0.05, help="trust level at which giving is halved; 0=trust doesn't gate giving")
    ap.add_argument("--opinion_noise", type=float, default=0.03, help="daily personal opinion drift (sd); 0=none")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--animate", type=int, default=0, help="1 to output agents_anim.gif")
    ap.add_argument("--frameskip", type=int, default=3)
    ap.add_argument("--outdir", type=str, default="outputs/exp1")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    p = Params(
        N=args.N, share_minority=args.minority_share, days=args.days,
        base_majority=args.base_majority, base_minority=args.base_minority,
        survival_floor=args.survival_floor, lambda_=args.lambda_,
        engagement=args.engagement, p_edge=args.p_edge, shock_sd=args.shock_sd,
        homophily=args.homophily, opinion_altruism=args.opinion_altruism,
        opinion_trust=args.opinion_trust, extremity_susceptibility=args.extremity_susceptibility,
        trust_half=args.trust_half, opinion_noise=args.opinion_noise, seed=args.seed
    )
    sim = Simulation(p)
    df = sim.run()

    # Save metrics
    metrics_path = os.path.join(args.outdir, "metrics.csv")
    df.to_csv(metrics_path, index=False)

    # Plots
    plot_metrics(df, args.outdir)

    # Optional animation
    if args.animate:
        # generate simple traces (random fixed layout)
        rng = np.random.default_rng(args.seed)
        x = rng.random(p.N)
        y = rng.random(p.N)
        traces = []
        # reconstruct approximate per-day resources path from metrics proxies isn't available;
        # so we approximate sizes uniformly here for demo purposes.
        # If you want exact resources per day, extend Simulation to record them.
        mean_res = np.ones(p.days)  # placeholder for size scaling
        for day in range(p.days):
            # simple stand-in vector; could be enhanced to track real per-agent states
            traces.append({"day": int(df.iloc[day]["day"]), "x": x, "y": y,
                           "affiliation": None, "resources": np.ones(p.N)})
        animate_agents(traces, args.outdir, frameskip=args.frameskip)

    print(f"Saved metrics and plots to: {args.outdir}")

if __name__ == "__main__":
    main()
