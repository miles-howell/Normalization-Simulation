
# Normalization vs. Outliers — Primer-style Simulation

This project simulates how **AI-driven normalization** and **outlier movements** (e.g., social justice groups, political extremists, environmentalists, anti-vax misinformation, religious cults) interact with a simple resource economy and societal metrics.

It’s designed to be **simple, hackable, and visual**—ideal for iterative experiments or a YouTube-style explainer.

## Features
- Agents split into **majority** and **minority** (with unequal daily incomes).
- A **persistent resource economy**: agents earn, help each other, eat, and carry savings over to the next day (see below).
- **Outlier archetypes** that affect altruism, trust, cross-group interactions, polarization, and policy pressure.
- **Normalization dial (lambda)**: pull opinions toward the mean (or flip to an **engagement mode** that amplifies extremes).
- **Opinions feed back into behavior** (see below), so the normalization dial moves trust, starvation and stability, not just opinion stats.
- Daily **resource shocks** (good/bad harvest days) so mutual aid actually matters.
- Track metrics each day: **stability**, **inequality (Gini)**, **opinion diversity (entropy)**, **affiliation diversity**, **average trust**, **starvation rate** (minority, majority and overall), **opinion mean/std**.
- Save **CSV metrics** and **matplotlib plots**.

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

## Dials (CLI flags)
- `--N` (agents, default 240)
- `--days` (time steps)
- `--lambda_` (normalization strength; 0=no damping, higher=faster convergence)
- `--engagement` (0=normalize toward mean, 1=amplify away from mean)
- `--minority_share` (fraction of minority agents; default 0.3)
- `--base_majority` (default 1.0), `--base_minority` (default 0.4): daily income of each group
- `--survival_floor` (default 0.5): daily consumption; an agent with less than this on hand is starving
- `--resource_decay` (default 0.1): share of savings lost each day (spoilage/depreciation); 1 = no savings
- `--shock_sd` (daily lognormal resource shock; default 0.25, 0=none)
- `--homophily`, `--opinion_altruism`, `--opinion_trust`, `--extremity_susceptibility`, `--trust_half` (opinion feedback strengths; see below)
- `--opinion_noise` (daily personal opinion drift; default 0.03, 0=none)
- `--seed` (random seed)
- `--outdir` (where to save outputs)

## Resource economy
Each agent holds a stock of resources that carries over from day to day. Every day:

1. **Income**: base income (`--base_majority` / `--base_minority`, raised by the public good) times a lognormal shock (`--shock_sd`). Environmentalists' public-good investment is taken out of income.
2. **On hand** = savings + today's income.
3. **Mutual aid**: each agent meets one neighbor and can give up to the amount that brings the neighbor up to `--survival_floor` (giving capacity is described in the next section).
4. **Metrics** are taken on what agents have on hand after aid: anyone below `--survival_floor` is starving, and inequality is the Gini of these amounts.
5. **Consumption**: everyone eats `--survival_floor`, the remainder (at least 0) loses `--resource_decay` and becomes tomorrow's savings.

Intended baseline: the majority earns twice its needs (1.0 vs. 0.5) and builds savings, which levels off at roughly `(base - (1 - decay) · floor) / decay` on hand, about 5.5 with the defaults.
The minority earns 0.4, **clearly below the 0.5 floor by design**: it cannot save and depends on aid every day, so its starvation rate measures how much help reaches it.
Because the shortfall is built in rather than sitting exactly on the floor, nudging `--base_minority` by ±0.01 shifts minority starvation by only a few points.
Putting `--base_minority` right at the floor with `--shock_sd 0` still gives a cliff, because every minority agent is then identical; with the default shocks the curve is smooth there too.

Inequality starts at about 0.23 (income gap plus shocks) and rises to about 0.31 over the first ~10 days as majority savings build up.
After that it is set by how much income the minority has: policy dials (`policy_push` in `outliers_config.py`) that move `base_minority` towards or above the floor pull it down sharply, and those that push it lower raise it.
Aid only tops agents up to the floor and so moves starvation far more than inequality.

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

Each agent's opinion also drifts a little every day (`--opinion_noise`, default 0.03), standing in for personal experience.
Without it, neighbor averaging alone collapses opinions to consensus at any lambda, so the dial would have nothing to act on.
With it, opinion spread settles where the drift balances the pull toward consensus, so each lambda gives its own level of spread, and through the feedback above its own trust and starvation.
At `lambda_=0` there is a tipping loop: spread erodes trust, low trust weakens neighbor averaging, and opinions drift toward the poles.

Typical results (150 days, mean of the last 50 days over seeds 3, 7, 11, 23, 42, 99):

| run | opinion_std | stability | avg_trust | minority_starvation_rate | overall_starvation_rate |
|---|---|---|---|---|---|
| `--lambda_ 0` | 0.482 | 0.520 | 0.129 | 0.687 | 0.206 |
| `--lambda_ 0.05` | 0.127 | 0.523 | 0.166 | 0.660 | 0.198 |
| `--lambda_ 0.15` | 0.055 | 0.525 | 0.195 | 0.642 | 0.193 |
| `--lambda_ 0.5` | 0.034 | 0.527 | 0.213 | 0.624 | 0.187 |
| `--lambda_ 0.15 --engagement 1` | 0.981 | 0.515 | 0.057 | 0.740 | 0.222 |

Stronger normalization means more trust, less starvation and slightly more stability. Engagement mode is worse than no normalization.
At `lambda_ 0` the tipping loop decides the outcome, so results there vary most between seeds (opinion_std 0.32–0.73).
Stability only moves a little in any setting: it is dominated by the gap between majority savings and the minority's hand-to-mouth income. Inequality sits at about 0.31 in all five runs for the same reason.

## Outputs
- `metrics.csv` with all tracked metrics.
- `metrics_over_time.png` (stability, trust, 1-inequality).
- `diversity_and_minority.png` (minority and majority starvation rates, opinion & affiliation diversity).

Metric definitions:
- `minority_starvation_rate` / `majority_starvation_rate`: share of that group whose resources on hand (savings + income + aid) are below `survival_floor`, i.e. who can't cover the day's consumption. `overall_starvation_rate` is the same over everyone. The minority rate is empty (NaN) when `--minority_share 0`.
- `inequality`: Gini coefficient of resources on hand (before consumption).
- `stability` = `1 - 0.7·CV(resources on hand) - 0.3·overall_starvation_rate`, clipped to [0, 1].
- `diversity`: opinions are cut into 10 equal bins over [-1, 1]; Shannon entropy of the bin shares divided by `log2(10)`. 1 means spread evenly over all 10 bins; two equally full bins give 0.30.
- `affil_entropy`: the same over the 6 affiliations (5 archetypes plus `"none"`), divided by `log2(6)`.

## Notes
- This is **not** a real social prediction engine; it’s a **teaching toy** to visualize tradeoffs.
- Everything is modular—tweak `outliers_config.py` and the knobs in `run_cli.py`.
- You can build Primer-style episodes by fixing a few dials and narrating the trajectories.

MIT License.
