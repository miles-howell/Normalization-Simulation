
# Normalization vs. Outliers — Primer-style Simulation

This project simulates how **AI-driven normalization** and **outlier movements** (e.g., social justice groups, political extremists, environmentalists, anti-vax misinformation, religious cults) interact with a simple resource economy and societal metrics.

It’s designed to be **simple, hackable, and visual**—ideal for iterative experiments or a YouTube-style explainer.

## Features
- Agents split into **majority** and **minority** (with unequal daily incomes).
- A **persistent resource economy**: agents earn, help each other, eat, and carry savings over to the next day (see below).
- **Outlier archetypes** that affect altruism, trust, cross-group interactions, polarization, and policy pressure.
- **Normalization dial (lambda)**: pull opinions toward the mean (or flip to an **engagement mode** that amplifies extremes).
- **Opinions feed back into behavior** (see below), so opinions can move trust, starvation and stability, not just opinion stats.
- Daily **resource shocks** (good/bad harvest days) so mutual aid actually matters.
- Track metrics each day: **stability**, **inequality (Gini)**, **opinion diversity (entropy)**, **affiliation diversity**, **average trust** (overall, in-group and out-group), **starvation rate** (minority, majority and overall), **opinion mean/std**.
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
- `--trust_gain` (default 0.02), `--trust_loss` (default 0.02), `--trust_reversion` (default 0.02): how trust responds to help and refusals and how fast it returns to baseline (see "Trust" below)
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

## Trust
Each agent has a baseline trust (drawn from N(0.6, 0.1) at the start) and two working trust levels:
**in-group trust**, toward agents whose opinion is on the same side of 0, and **out-group trust**, toward agents on the other side.
Both start at the baseline. Whenever the two agents meet, the in-group or out-group value is used depending on whether they are in the same camp.

Trust only moves when cooperation matters, i.e. when the neighbor an agent meets needs help (has less than `--survival_floor` on hand):

- The **asker's** trust in the giver's camp rises by `trust_gain` times the share of its need that was covered, and falls by `trust_loss + opinion_trust · d` times the share that was refused. Full help is a pure gain, an outright refusal a pure loss, partial help is in between.
- The **giver's** trust rises by a quarter of `trust_gain` when it helps. A refuser's trust doesn't change.
- Meetings where nobody needs anything leave trust unchanged. With the defaults about 80% of meetings are like that, and they used to erode trust on their own.
- Outlier archetypes add their `trust_delta` to these changes. A positive value (trust boost) applies to every camp; a negative one (suspicion) only toward the other camp.
- Every day both values move `--trust_reversion` (2%) of the way back to the agent's baseline, since generalized trust is a slow-moving, fairly stable trait.

Trust therefore settles where the help an agent receives and the refusals it meets balance the pull back to its baseline.
Only agents who need help (in practice the minority) see their trust move much; the majority rarely needs help, so its trust stays close to baseline, rising slightly from giving.
Trust in the other camp ends up lower than in the own camp, because asks across camps involve larger opinion distances and archetype suspicion.

## How opinions feed back into the model
Opinions live in [-1, 1]; the distance between two agents' opinions is `d = |o_i - o_j|` (0..2).
Each day the normalization dial (`--lambda_`, `--engagement`) reshapes opinions, and opinions in turn shape:

| Mechanism | Rule | Flag (default) |
|---|---|---|
| Homophily | Partner choice weight × `exp(-homophily · d)` | `--homophily` (2.0) |
| Altruism | Giving capacity × `1 - opinion_altruism · d/2` (people help those they agree with) | `--opinion_altruism` (1.0) |
| Trust | When help is refused, the asker's trust drops by an extra `opinion_trust · d` | `--opinion_trust` (0.03) |
| Contagion | Outlier recruitment probability × `(1-w) + w · |o_i - mean| / 0.2`: agents far from the mainstream are easier to recruit, consensus slows recruitment | `--extremity_susceptibility` (0.8) |
| Trust gates giving | Giving capacity × `trust / (trust + trust_half)`, using the giver's in- or out-group trust: low-trust agents stop sharing, so the trust effect reaches resources | `--trust_half` (0.05) |

The intended causal chain: normalization → small opinion distances → more giving and fewer refusals → more trust and aid → lower starvation and higher stability.
Engagement mode pushes agents apart → help across the divide stops, out-group trust falls, recruitment into outlier groups speeds up → higher starvation, lower stability.
Neighbor averaging also uses trust (each day an agent moves `(trust_ij + trust_ji)/4` of the way to a random neighbor's opinion), so trust feeds back into opinions.
Setting `homophily`, `opinion_altruism`, `opinion_trust` and `extremity_susceptibility` to 0 decouples opinions from everything else.

Each agent's opinion also drifts a little every day (`--opinion_noise`, default 0.03), standing in for personal experience.
Without it, neighbor averaging alone collapses opinions to consensus at any lambda, so the dial would have nothing to act on.
With it, opinion spread settles where the drift balances the pull toward consensus, so each lambda gives its own level of spread.

Typical results (150 days, mean of the last 50 days over seeds 3, 7, 11, 23, 42, 99):

| run | opinion_std | stability | avg_trust | avg_trust_in | avg_trust_out | minority_starvation_rate | overall_starvation_rate |
|---|---|---|---|---|---|---|---|
| `--lambda_ 0` | 0.053 | 0.538 | 0.611 | 0.662 | 0.560 | 0.523 | 0.157 |
| `--lambda_ 0.05` | 0.048 | 0.540 | 0.614 | 0.663 | 0.565 | 0.507 | 0.152 |
| `--lambda_ 0.15` | 0.042 | 0.536 | 0.612 | 0.658 | 0.566 | 0.536 | 0.161 |
| `--lambda_ 0.5` | 0.033 | 0.538 | 0.623 | 0.667 | 0.580 | 0.519 | 0.156 |
| `--lambda_ 0.15 --engagement 1` | 0.185 | 0.536 | 0.606 | 0.653 | 0.560 | 0.540 | 0.162 |

Trust settles within the run (the last 50 days differ from the 50 before by less than 0.01), no agent's trust falls below 0.05, and the six seeds agree to within ±0.02.
**The dial now has only a small effect.** Before trust was fixed, trust eroded on every meeting and fell to 0.06–0.21; low trust weakened neighbor averaging, which let the dial spread opinions out (std 0.48 at `lambda_ 0`, 0.98 in engagement mode), and weak trust then cut aid through `trust_half`.
With trust held near its baseline, neighbor averaging (about 30% of the way to a neighbor each day) dominates the opinion dynamics, so even `lambda_ 0` stays near consensus, and engagement mode reaches only 0.19 (0.10–0.31 between seeds).
Opinion distance therefore rarely causes refusals: with `homophily 2` polarized agents mostly meet like-minded neighbors anyway.
Stronger normalization still gives slightly more trust, and engagement slightly less, but the starvation differences between settings are within seed noise.
Weaker influence (issue #16) and a feed that acts on exposure and out-group trust (issue #17) are the planned ways to restore a visible effect.
Stability and inequality (about 0.31) are dominated by the gap between majority savings and the minority's hand-to-mouth income in every setting.

## Outputs
- `metrics.csv` with all tracked metrics.
- `metrics_over_time.png` (stability, average/in-group/out-group trust, 1-inequality).
- `diversity_and_minority.png` (minority and majority starvation rates, opinion & affiliation diversity).

Metric definitions:
- `minority_starvation_rate` / `majority_starvation_rate`: share of that group whose resources on hand (savings + income + aid) are below `survival_floor`, i.e. who can't cover the day's consumption. `overall_starvation_rate` is the same over everyone. The minority rate is empty (NaN) when `--minority_share 0`.
- `avg_trust_in` / `avg_trust_out`: mean in-group and out-group trust over all agents; `avg_trust` is the mean of the two.
- `inequality`: Gini coefficient of resources on hand (before consumption).
- `stability` = `1 - 0.7·CV(resources on hand) - 0.3·overall_starvation_rate`, clipped to [0, 1].
- `diversity`: opinions are cut into 10 equal bins over [-1, 1]; Shannon entropy of the bin shares divided by `log2(10)`. 1 means spread evenly over all 10 bins; two equally full bins give 0.30.
- `affil_entropy`: the same over the 6 affiliations (5 archetypes plus `"none"`), divided by `log2(6)`.

## Notes
- This is **not** a real social prediction engine; it’s a **teaching toy** to visualize tradeoffs.
- Everything is modular—tweak `outliers_config.py` and the knobs in `run_cli.py`.
- You can build Primer-style episodes by fixing a few dials and narrating the trajectories.

MIT License.
