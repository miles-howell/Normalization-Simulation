
import os
import argparse
import pandas as pd
from .sim import Params, Simulation
from .plots import plot_metrics

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--N", type=int, default=240)
    ap.add_argument("--days", type=int, default=150)
    ap.add_argument("--lambda_", type=float, default=0.15)
    ap.add_argument("--engagement", type=int, default=0, help="0=normalize to mean, 1=amplify extremes")
    ap.add_argument("--minority_share", type=float, default=0.3)
    ap.add_argument("--base_majority", type=float, default=1.0)
    ap.add_argument("--base_minority", type=float, default=0.4)
    ap.add_argument("--survival_floor", type=float, default=0.5, help="daily consumption; less than this on hand = starving")
    ap.add_argument("--resource_decay", type=float, default=0.1, help="share of savings lost each day; 1=no savings")
    ap.add_argument("--p_edge", type=float, default=0.06)
    ap.add_argument("--shock_sd", type=float, default=0.25, help="daily resource shock (lognormal sd); 0=none")
    ap.add_argument("--homophily", type=float, default=2.0, help="preference for like-minded partners")
    ap.add_argument("--opinion_altruism", type=float, default=1.0, help="how much opinion distance cuts giving")
    ap.add_argument("--opinion_trust", type=float, default=0.03, help="extra trust loss per unit opinion distance when help is refused")
    ap.add_argument("--extremity_susceptibility", type=float, default=0.8, help="0..1; how much distance from the mean drives outlier recruitment")
    ap.add_argument("--trust_half", type=float, default=0.05, help="trust level at which giving is halved; 0=trust doesn't gate giving")
    ap.add_argument("--opinion_noise", type=float, default=0.03, help="daily personal opinion drift (sd); 0=none")
    ap.add_argument("--trust_gain", type=float, default=0.02, help="asker's trust gain when its need is fully covered")
    ap.add_argument("--trust_loss", type=float, default=0.02, help="asker's trust loss when it gets no help")
    ap.add_argument("--trust_reversion", type=float, default=0.02, help="share of the gap to baseline trust closed each day; 0=none")
    ap.add_argument("--disaster_days", type=int, nargs="*", default=[], help="days on which a disaster strikes, e.g. --disaster_days 60 100")
    ap.add_argument("--disaster_severity", type=float, default=0.5, help="share of resources on hand destroyed if the response fails")
    ap.add_argument("--disaster_threshold", type=float, default=0.5, help="cooperation (lowest camp's mean out-group trust) the response needs")
    ap.add_argument("--disaster_mitigation", type=float, default=0.75, help="share of the damage a working response prevents")
    ap.add_argument("--disaster_trust_shift", type=float, default=0.05, help="out-group trust gained/lost when the response works/fails")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--outdir", type=str, default="outputs/exp1")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    p = Params(
        N=args.N, share_minority=args.minority_share, days=args.days,
        base_majority=args.base_majority, base_minority=args.base_minority,
        survival_floor=args.survival_floor, resource_decay=args.resource_decay, lambda_=args.lambda_,
        engagement=args.engagement, p_edge=args.p_edge, shock_sd=args.shock_sd,
        homophily=args.homophily, opinion_altruism=args.opinion_altruism,
        opinion_trust=args.opinion_trust, extremity_susceptibility=args.extremity_susceptibility,
        trust_half=args.trust_half, opinion_noise=args.opinion_noise, trust_gain=args.trust_gain,
        trust_loss=args.trust_loss, trust_reversion=args.trust_reversion,
        disaster_days=tuple(args.disaster_days), disaster_severity=args.disaster_severity,
        disaster_threshold=args.disaster_threshold, disaster_mitigation=args.disaster_mitigation,
        disaster_trust_shift=args.disaster_trust_shift, seed=args.seed
    )
    sim = Simulation(p)
    df = sim.run()

    # Save metrics
    metrics_path = os.path.join(args.outdir, "metrics.csv")
    df.to_csv(metrics_path, index=False)

    # Plots
    plot_metrics(df, args.outdir)

    print(f"Saved metrics and plots to: {args.outdir}")

if __name__ == "__main__":
    main()
