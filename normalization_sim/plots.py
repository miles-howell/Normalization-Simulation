
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

def plot_metrics(df, outdir):
    os.makedirs(outdir, exist_ok=True)
    # Figure 1
    plt.figure(figsize=(8,4))
    plt.plot(df["day"], df["stability"], label="Stability")
    plt.plot(df["day"], df["avg_trust"], label="Avg Trust")
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
    plt.plot(df["day"], df["diversity"], label="Opinion Diversity (entropy)")
    plt.plot(df["day"], df["affil_entropy"], label="Affiliation Diversity (entropy)")
    plt.legend()
    plt.title("Minority Outcomes and Diversity Over Time")
    plt.xlabel("Day")
    plt.ylabel("Rate / Entropy")
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "diversity_and_minority.png"))
    plt.close()

def animate_agents(traces, outdir, frameskip=3, filename="agents_anim.gif"):
    """traces: list of dict(day=int, x=np.array, y=np.array, affiliation=np.array, resources=np.array)
    Creates a simple GIF of agent states over time (downsampled by frameskip).
    """
    os.makedirs(outdir, exist_ok=True)
    xs = traces[0]["x"]
    ys = traces[0]["y"]

    fig, ax = plt.subplots(figsize=(6,6))
    scat = ax.scatter(xs, ys, s=20)
    ax.set_title("Agents Over Time")
    ax.set_xlim(0,1); ax.set_ylim(0,1)
    ax.set_xticks([]); ax.set_yticks([])

    def update(frame_idx):
        t = traces[frame_idx]
        # map resources to size for visual interest
        sizes = 10 + 40 * (t["resources"] / (t["resources"].mean() + 1e-9))
        scat.set_offsets(np.column_stack([t["x"], t["y"]]))
        scat.set_sizes(sizes)
        ax.set_title(f"Agents Over Time — Day {t['day']}")
        return scat,

    idxs = list(range(0, len(traces), max(frameskip,1)))
    anim = FuncAnimation(fig, update, frames=idxs, blit=True)
    outpath = os.path.join(outdir, filename)
    anim.save(outpath, writer=PillowWriter(fps=6))
    plt.close(fig)
    return outpath
