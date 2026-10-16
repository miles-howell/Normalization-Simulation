
import os
import matplotlib.pyplot as plt

def plot_metrics(df, outdir):
    os.makedirs(outdir, exist_ok=True)
    # Figure 1
    plt.figure(figsize=(8,4))
    plt.plot(df["day"], df["stability"], label="Stability")
    plt.plot(df["day"], df["avg_trust"], label="Avg Trust")
    plt.plot(df["day"], df["avg_trust_in"], label="In-group Trust", linestyle=":")
    plt.plot(df["day"], df["avg_trust_out"], label="Out-group Trust", linestyle="--")
    plt.plot(df["day"], 1 - df["inequality"], label="(1 - Inequality)")
    plt.legend()
    plt.title("Stability, Trust, and (1 - Inequality) Over Time")
    plt.xlabel("Day")
    plt.ylabel("Score")
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "metrics_over_time.png"))
    plt.close()

    # Figure 2
    plt.figure(figsize=(8,4))
    plt.plot(df["day"], df["minority_starvation_rate"], label="Minority Starvation Rate")
    plt.plot(df["day"], df["majority_starvation_rate"], label="Majority Starvation Rate", linestyle="--")
    plt.plot(df["day"], df["diversity"], label="Opinion Diversity (entropy / log2 10 bins)")
    plt.plot(df["day"], df["affil_entropy"], label="Affiliation Diversity (entropy / log2 6 groups)")
    plt.legend()
    plt.title("Starvation by Group and Diversity Over Time")
    plt.xlabel("Day")
    plt.ylabel("Rate / Normalized Entropy")
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "diversity_and_minority.png"))
    plt.close()
