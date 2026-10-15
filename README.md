
# Normalization vs. Outliers — Primer-style Simulation

This project simulates how **AI-driven normalization** and **outlier movements** (e.g., social justice groups, political extremists, environmentalists, anti-vax misinformation, religious cults) interact with a simple resource economy and societal metrics.

It’s designed to be **simple, hackable, and visual**—ideal for iterative experiments or a YouTube-style explainer.

## Features
- Agents split into **majority** and **minority** (with unequal base resources).
- **Outlier archetypes** that affect altruism, trust, cross-group interactions, polarization, and policy pressure.
- **Normalization dial (lambda)**: pull opinions toward the mean (or flip to an **engagement mode** that amplifies extremes).
- **Opinions feed back into behavior** (see below), so the normalization dial moves trust, starvation and stability, not just opinion stats.
- Daily **resource shocks** (good/bad harvest days) so mutual aid actually matters.
- Track metrics each day: **stability**, **inequality (Gini)**, **opinion diversity (entropy)**, **affiliation diversity**, **average trust**, **minority starvation rate**, **opinion mean/std**.
- Save **CSV metrics** and **matplotlib plots**. Optional **GIF animation** of agent states over time.

## Quick Start
1. **Requirements** (Python 3.9+):
    ```bash
    pip install -r requirements.txt
    ```

2. **Run a simulation** (CSV + plots in `./outputs/exp1`):
    ```bash
    python -m normalization_sim.run_cli --days 150 --lambda_ 0.15 --minority_share 0.3 --seed 7 --outdir outputs/exp1
    ```
    - To try **engagement mode** (push away from the mean):
    ```bash
    python -m normalization_sim.run_cli --days 150 --lambda_ 0.15 --engagement 1 --outdir outputs/engage_demo
    ```

3. **Animate agents** (optional; writes a GIF, slower):
    ```bash
    python -m normalization_sim.run_cli --days 150 --animate 1 --frameskip 3 --outdir outputs/anim_demo
    ```

## Dials (CLI flags)
- `--N` (agents, default 240)
- `--days` (time steps)
- `--lambda_` (normalization strength; 0=no damping, higher=faster convergence)
- `--engagement` (0=normalize toward mean, 1=amplify away from mean)
- `--minority_share` (fraction of minority agents; default 0.3)
- `--base_majority` (default 1.0), `--base_minority` (default 0.5), `--survival_floor` (default 0.5)
- `--shock_sd` (daily lognormal resource shock; default 0.25, 0=none)
- `--homophily`, `--opinion_altruism`, `--opinion_trust`, `--extremity_susceptibility`, `--trust_half` (opinion feedback strengths; see below)
- `--seed` (random seed)
- `--animate` (0/1) and `--frameskip` (plot every k days)
- `--outdir` (where to save outputs)

## How opinions feed back into the model
Opinions live in [-1, 1]; the distance between two agents' opinions is `d = |o_i - o_j|` (0..2).
Each day the normalization dial (`--lambda_`, `--engagement`) reshapes opinions, and opinions in turn shape:

| Mechanism | Rule | Flag (default) |
|---|---|---|
| Homophily | Partner choice weight × `exp(-homophily · d)` | `--homophily` (2.0) |
| Altruism | Giving capacity × `1 - opinion_altruism · d/2` (people help those they agree with) | `--opinion_altruism` (1.0) |
| Trust | When no help flows, trust drops by an extra `opinion_trust · d` | `--opinion_trust` (0.03) |
| Contagion | Outlier recruitment probability × `(1-w) + w · |o_i - mean| / 0.2`: agents far from the mainstream are easier to recruit, consensus slows recruitment | `--extremity_susceptibility` (0.8) |
| Trust gates giving | Giving capacity × `trust / (trust + trust_half)`: low-trust agents stop sharing, so the trust effect reaches resources | `--trust_half` (0.05) |

The causal chain: normalization → small opinion distances → more giving and less trust erosion → more aid → lower starvation and higher stability.
Engagement mode pushes agents to opposite poles → help across the divide stops, trust collapses, recruitment into outlier groups speeds up → higher starvation, lower stability.
Setting `homophily`, `opinion_altruism`, `opinion_trust` and `extremity_susceptibility` to 0 decouples opinions from everything else.

Typical results (150 days, mean of the last 50 days over seeds 7, 11, 23):

| run | stability | avg_trust | starvation |
|---|---|---|---|
| `--lambda_ 0` | 0.703 | 0.183 | 0.134 |
| `--lambda_ 0.15` | 0.699 | 0.181 | 0.140 |
| `--lambda_ 0.5` | 0.701 | 0.199 | 0.136 |
| `--lambda_ 0.15 --engagement 1` | 0.692 | 0.026 | 0.157 |

Normalize vs. engage is the big split. Within normalize mode, the opinion averaging already pulls opinions together at `lambda_=0`, so higher lambda mainly speeds convergence and lifts trust; its effect on starvation is about the size of seed-to-seed noise.

## Outputs
- `metrics.csv` with all tracked metrics.
- `metrics_over_time.png` (stability, trust, 1-inequality).
- `diversity_and_minority.png` (minority starvation rate, opinion & affiliation diversity).
- Optional: `agents_anim.gif` (animation).

## Notes
- This is **not** a real social prediction engine; it’s a **teaching toy** to visualize tradeoffs.
- Everything is modular—tweak `outliers_config.py` and the knobs in `run_cli.py`.
- You can build Primer-style episodes by fixing a few dials and narrating the trajectories.

MIT License.
