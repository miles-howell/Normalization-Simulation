
# Normalization vs. Outliers — Primer-style Simulation

This project simulates how **AI-driven normalization** and **outlier movements** (e.g., social justice groups, political extremists, environmentalists, anti-vax misinformation, religious cults) interact with a simple resource economy and societal metrics.

It’s designed to be **simple, hackable, and visual**—ideal for iterative experiments or a YouTube-style explainer.

## Features
- Agents split into **majority** and **minority** (with unequal daily incomes).
- A **persistent resource economy**: agents earn, help each other, eat, and carry savings over to the next day (see below).
- **Outlier archetypes** that affect altruism, trust, cross-group interactions, polarization, and policy pressure.
- **Normalization dial (lambda)**: pull opinions toward the mean (or flip to an **engagement mode** that amplifies extremes).
- **Anchored opinions with bounded confidence** (Friedkin–Johnsen): agents keep being pulled back to their initial view and ignore partners whose opinions are too far from their own (see "Opinion dynamics").
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
- `--influence` (default 0.05), `--epsilon` (default 0.5), `--stubbornness` (default 0.1): how strongly partners pull on opinions, how far apart two opinions can be before the partner is ignored, and how strongly agents hold on to their initial view (see "Opinion dynamics" below)
- `--opinion_noise` (daily personal opinion drift; default 0, i.e. none)
- `--trust_gain` (default 0.02), `--trust_loss` (default 0.02), `--trust_reversion` (default 0.02): how trust responds to help and refusals and how fast it returns to baseline (see "Trust" below)
- `--disaster_days` (days on which a disaster strikes, e.g. `--disaster_days 60 100`; default none), `--disaster_severity` (0.5), `--disaster_threshold` (0.5), `--disaster_mitigation` (0.75), `--disaster_trust_shift` (0.05) (see "Disasters" below)
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

## Disasters
A disaster is a hazard that can only be handled if both opinion camps work together.
Disasters never happen on their own: they strike on the days listed in `--disaster_days`, or at the start of the next step after calling `Simulation.trigger_disaster()` from code.

When one strikes (before the day's mutual aid):

1. **Cooperation** is measured as the mean out-group trust of the less willing camp (agents are willing to work with the other camp as far as they trust it). If everyone is in one camp, mean in-group trust is used instead.
2. If cooperation reaches `--disaster_threshold` the joint response works and prevents `--disaster_mitigation` of the damage; otherwise it fails.
3. Everyone loses `--disaster_severity` of their resources on hand (savings plus today's income), reduced by the mitigation if the response worked: 12.5% instead of 50% with the defaults.
4. Working together raises everyone's out-group trust by `--disaster_trust_shift`; failing together lowers it by the same amount. Repeated failures therefore make the next response more likely to fail.

The disaster days are marked with gray vertical lines in both plots.
These defaults are not tuned: with today's opinion dynamics cooperation sits between 0.52 and 0.59 after 150 days, so with the default threshold the response still works in every dial setting, though with less margin than before.
The mechanism is meant to become more informative once the dial produces real clusters (issue #17); a policy for when disasters strike automatically is left for later.

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
Setting `homophily`, `opinion_altruism`, `opinion_trust` and `extremity_susceptibility` to 0 decouples opinions from everything else.

## Opinion dynamics
Core attitudes are sticky, persuasion effects are small, and people give little weight to views far from their own.
Opinions therefore follow a Friedkin–Johnsen model with bounded confidence. Every day, each agent:

1. **Meets one partner**, chosen the same way as the aid partner (homophily and the archetypes' `cross_pref`).
2. **Bounded confidence**: if the partner's opinion is within `--epsilon` (0.5) of its own, it moves `influence · (trust_ij + trust_ji)/2` of the way toward it: about 3% a day at typical trust, with `--influence 0.05`. A partner further away has no effect; there is no repulsion (evidence for a backfire effect is weak).
3. The archetypes' `polarization` and the normalization dial (`--lambda_`, `--engagement`) then push opinions toward or away from the population mean, as before.
4. **Anchoring**: each agent keeps its initial opinion as an anchor and a personal stubbornness `s_i`, drawn from N(`--stubbornness`, `--stubbornness`/2) clipped to [0, 1]. The new opinion is `s_i · anchor + (1 - s_i) · (result of steps 2–3)`.
5. Optional personal drift `--opinion_noise` (default 0) is added, and opinions are clipped to [-1, 1].

Because of the anchors, opinions no longer collapse to consensus and need no noise to stay apart: the settled spread comes from how spread out the anchors are, and agents keep their own views (the correlation between an agent's final opinion and its anchor averages 0.79–0.98, depending on the dial).
With the dial off and no outlier groups, peer influence and anchoring alone take about six weeks (39–47 days) to settle, at a spread of about 0.20 (from 0.25 at the start).
Raising `--epsilon` or lowering `--stubbornness` narrows the spread, the reverse widens it (6 seeds, last 50 days):

| change from the defaults | opinion_std at `--lambda_ 0.05` | opinion_std at `--lambda_ 0.15` |
|---|---|---|
| `--epsilon 0.25` | 0.248 | 0.123 |
| (defaults) | 0.219 | 0.117 |
| `--epsilon 1.0` | 0.203 | 0.117 |
| `--stubbornness 0.2` | 0.235 | 0.163 |
| `--stubbornness 0.05` | 0.191 | 0.076 |

`epsilon` matters little at `--lambda_ 0.15` because the dial keeps almost every partner within 0.5.

Typical results (150 days, mean of the last 50 days over seeds 3, 7, 11, 23, 42, 99; "settles by" is the first day after which `opinion_std` stays closer to its final level than 10% of its total change; mean and range over the seeds):

| run | opinion_std | settles by (day) | anchor corr. | stability | avg_trust | avg_trust_in | avg_trust_out | minority_starvation_rate | overall_starvation_rate |
|---|---|---|---|---|---|---|---|---|---|
| `--lambda_ 0` | 0.570 | still rising | 0.87 | 0.535 | 0.595 | 0.639 | 0.550 | 0.544 | 0.163 |
| `--lambda_ 0.05` | 0.219 | 132 (87–150) | 0.98 | 0.535 | 0.599 | 0.648 | 0.549 | 0.540 | 0.162 |
| `--lambda_ 0.15` | 0.117 | 19 (6–25) | 0.95 | 0.536 | 0.599 | 0.646 | 0.552 | 0.536 | 0.161 |
| `--lambda_ 0.5` | 0.050 | 3 | 0.92 | 0.536 | 0.611 | 0.654 | 0.568 | 0.536 | 0.161 |
| `--lambda_ 0.15 --engagement 1` | 0.991 | 29 (26–31) | 0.79 | 0.533 | 0.622 | 0.662 | 0.581 | 0.565 | 0.169 |

**The dial and the archetypes now drive opinion spread, not peer influence.** Peer influence used to move an agent about 30% of the way to a random neighbor each day, which kept every setting near consensus (std 0.03–0.05 with noise, 0.19 in engagement mode). At about 3% a day it is weaker than the society-wide pushes, so:

- **Normalization narrows the spread to a level that depends on lambda** (0.22 at 0.05, 0.12 at 0.15, 0.05 at 0.5) instead of a near-identical consensus. Because the dial pulls directly (15% of the way to the mean each day at 0.15), these settings still settle fast: 6–25 days at 0.15, 3 days at 0.5. Making the dial act through what people see is issue #17.
- **Without normalization the outlier groups polarize society.** The archetypes' `polarization` grows with their membership, and once nearly everyone has joined a group (issue #18) it pushes harder than the anchors pull back: at `--lambda_ 0` the spread is still rising at day 150 (0.57, up 0.07 on the 50 days before), and at 0.05 it creeps up until late in the run.
- **Engagement mode still pins nearly everyone at ±1**, because it is a direct 15%-a-day push away from the mean; issue #17 replaces it with a feed that goes through bounded confidence.

Trust settles within the run (the last 50 days differ from the 50 before by at most 0.015) and the six seeds agree to within ±0.03.
Because the anchors keep the two opinion camps apart, help across the divide is refused more often than before: 22–32 of the 240 agents (depending on the seed) end with out-group trust below 0.2, a few near 0. All of them are minority agents, nearly all in the archetypes with a negative `trust_delta` (political extremists, anti-vaxx, religious cult). No agent's in-group trust falls below 0.2.
The starvation differences between dial settings are still within seed noise; engagement mode is slightly worse.
Stability and inequality (about 0.31) are dominated by the gap between majority savings and the minority's hand-to-mouth income in every setting.

## Outputs
- `metrics.csv` with all tracked metrics.
- `metrics_over_time.png` (stability, average/in-group/out-group trust, 1-inequality).
- `diversity_and_minority.png` (minority and majority starvation rates, opinion & affiliation diversity).

Metric definitions:
- `minority_starvation_rate` / `majority_starvation_rate`: share of that group whose resources on hand (savings + income + aid) are below `survival_floor`, i.e. who can't cover the day's consumption. `overall_starvation_rate` is the same over everyone. The minority rate is empty (NaN) when `--minority_share 0`.
- `avg_trust_in` / `avg_trust_out`: mean in-group and out-group trust over all agents; `avg_trust` is the mean of the two.
- `disaster_loss`: share of resources on hand destroyed by a disaster that day (0 on days without one); `disaster_cooperation`: the cooperation level of that day's response (empty on days without one).
- `inequality`: Gini coefficient of resources on hand (before consumption).
- `stability` = `1 - 0.7·CV(resources on hand) - 0.3·overall_starvation_rate`, clipped to [0, 1].
- `diversity`: opinions are cut into 10 equal bins over [-1, 1]; Shannon entropy of the bin shares divided by `log2(10)`. 1 means spread evenly over all 10 bins; two equally full bins give 0.30.
- `affil_entropy`: the same over the 6 affiliations (5 archetypes plus `"none"`), divided by `log2(6)`.

## Notes
- This is **not** a real social prediction engine; it’s a **teaching toy** to visualize tradeoffs.
- Everything is modular—tweak `outliers_config.py` and the knobs in `run_cli.py`.
- You can build Primer-style episodes by fixing a few dials and narrating the trajectories.

MIT License.
