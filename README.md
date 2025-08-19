
# Normalization vs. Outliers — Primer-style Simulation

This project simulates how **AI-driven normalization** and **outlier movements** (e.g., social justice groups, political extremists, environmentalists, anti-vax misinformation, religious cults) interact with a simple resource economy and societal metrics.

It’s designed to be **simple, hackable, and visual**—ideal for iterative experiments or a YouTube-style explainer.

## Features
- Agents split into **majority** and **minority** (with unequal base resources).
- **Outlier archetypes** that affect altruism, trust, cross-group interactions, polarization, and policy pressure.
- **Normalization dial (lambda)**: pull opinions toward the mean (or flip to an **engagement mode** that amplifies extremes).
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
- `--seed` (random seed)
- `--animate` (0/1) and `--frameskip` (plot every k days)
- `--outdir` (where to save outputs)

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
