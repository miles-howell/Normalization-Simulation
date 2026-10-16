
# Normalization vs. Outliers — Primer-style Simulation

This project simulates how **AI-driven normalization** and **outlier movements** (e.g., social justice groups, political extremists, environmentalists, anti-vax misinformation, religious cults) interact with a simple resource economy and societal metrics.

It’s designed to be **simple, hackable, and visual**—ideal for iterative experiments or a YouTube-style explainer.

## Features
- Agents split into **majority** and **minority** (with unequal daily incomes).
- A **persistent resource economy**: agents earn, help each other, eat, and carry savings over to the next day (see below).
- **Outlier archetypes** that affect altruism, trust, cross-group interactions, polarization, and policy pressure.
- **Normalization dial (lambda)**: the share of attention agents give to an algorithmic **feed** rather than their peers. The feed shows mainstream content (normalizing) or, in **engagement mode**, content a bit more extreme than the viewer plus outrage that erodes trust in the other side (see "The feed").
- **Anchored opinions with bounded confidence** (Friedkin–Johnsen): agents keep being pulled back to their initial view and ignore partners whose opinions are too far from their own (see "Opinion dynamics").
- **Opinions feed back into behavior** (see below), so opinions can move trust, starvation and stability, not just opinion stats.
- Daily **resource shocks** (good/bad harvest days) so mutual aid actually matters.
- Track metrics each day: **stability**, **inequality (Gini)**, **opinion diversity (entropy)**, **affiliation diversity**, **average trust** (overall, in-group and out-group), **starvation rate** (minority, majority and overall), **opinion mean/std**, **share of opinions at the bounds**.
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
    - To try **engagement mode** (an engagement-optimized feed):
    ```bash
    python -m normalization_sim.run_cli --days 150 --lambda_ 0.15 --engagement 1 --outdir outputs/engage_demo
    ```

## Dials (CLI flags)
- `--N` (agents, default 240)
- `--days` (time steps)
- `--lambda_` (share of attention on the feed, 0..1; default 0.15; the rest goes to the peer network)
- `--engagement` (0=normalizing feed, 1=engagement feed)
- `--feed_influence` (default 0.2), `--feed_spread` (0.1), `--feed_push` (0.3), `--feed_outrage` (0.01): how strongly feed content moves opinions, how scattered it is, how much more extreme the engagement feed is than the viewer, and how fast its outrage erodes out-group trust (see "The feed" below)
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
These defaults are not tuned. With the normalizing feed, cooperation at the end of a 150-day run sits around 0.54, so the response works.
The engagement feed's outrage pulls it below the threshold (0.48 at `--lambda_ 0.15`, 0.32 at 0.5), so disasters there fail and each failure lowers out-group trust further (see "The feed").
A policy for when disasters strike automatically is left for later.

## How opinions feed back into the model
Opinions live in [-1, 1]; the distance between two agents' opinions is `d = |o_i - o_j|` (0..2).
Each day peers, the feed (`--lambda_`, `--engagement`) and the outlier groups reshape opinions, and opinions in turn shape:

| Mechanism | Rule | Flag (default) |
|---|---|---|
| Homophily | Partner choice weight × `exp(-homophily · d)` | `--homophily` (2.0) |
| Altruism | Giving capacity × `1 - opinion_altruism · d/2` (people help those they agree with) | `--opinion_altruism` (1.0) |
| Trust | When help is refused, the asker's trust drops by an extra `opinion_trust · d` | `--opinion_trust` (0.03) |
| Contagion | Outlier recruitment probability × `(1-w) + w · |o_i - mean| / 0.2`: agents far from the mainstream are easier to recruit, consensus slows recruitment | `--extremity_susceptibility` (0.8) |
| Trust gates giving | Giving capacity × `trust / (trust + trust_half)`, using the giver's in- or out-group trust: low-trust agents stop sharing, so the trust effect reaches resources | `--trust_half` (0.05) |

The intended causal chain: normalizing feed → small opinion distances → more giving and fewer refusals → more trust and aid → lower starvation and higher stability.
Engagement feed → two camps drift apart and outrage erodes out-group trust → help across the divide stops, joint disaster responses fail, recruitment into outlier groups speeds up → higher starvation, lower stability.

In practice the opinion and trust links are clearly visible, but the effect on starvation and stability is still within seed noise (see the results table under "The feed"): the minority's built-in income gap dominates both, and most aid already goes to like-minded partners.
Setting `homophily`, `opinion_altruism`, `opinion_trust` and `extremity_susceptibility` to 0 decouples opinions from everything else.

## Opinion dynamics
Core attitudes are sticky, persuasion effects are small, and people give little weight to views far from their own.
Opinions therefore follow a Friedkin–Johnsen model with bounded confidence. Every day, each agent:

1. **Meets one partner**, chosen the same way as the aid partner (homophily and the archetypes' `cross_pref`).
2. **Bounded confidence**: if the partner's opinion is within `--epsilon` (0.5) of its own, it moves `influence · (trust_ij + trust_ji)/2` of the way toward it: about 3% a day at typical trust, with `--influence 0.05`. A partner further away has no effect; there is no repulsion (evidence for a backfire effect is weak).
3. **Sees one feed item** (see "The feed"). Peer influence is weighted by `1 - lambda_` and the feed by `lambda_`, and feed content goes through the same bounded-confidence rule.
4. The archetypes' `polarization` then pushes opinions toward or away from the population mean, as before.
5. **Anchoring**: each agent keeps its initial opinion as an anchor and a personal stubbornness `s_i`, drawn from N(`--stubbornness`, `--stubbornness`/2) clipped to [0, 1]. The new opinion is `s_i · anchor + (1 - s_i) · (result of steps 2–4)`.
6. Optional personal drift `--opinion_noise` (default 0) is added, and opinions are clipped to [-1, 1].

Because of the anchors, opinions do not collapse to consensus and need no noise to stay apart: the settled spread comes from how spread out the anchors are, and agents keep their own views.
With no outlier groups and the default normalizing feed, peer influence, the feed and anchoring settle in about six weeks (33–48 days) at a spread of about 0.18 (from 0.25 at the start).
Raising `--epsilon` or lowering `--stubbornness` narrows the spread, the reverse widens it (no outlier groups, 6 seeds, last 50 days):

| change from the defaults | opinion_std, normalizing feed (`--lambda_ 0.15`) | opinion_std, engagement feed (`--lambda_ 0.5 --engagement 1`) |
|---|---|---|
| `--epsilon 0.25` | 0.225 | 0.300 |
| (defaults) | 0.184 | 0.472 |
| `--epsilon 1.0` | 0.172 | 0.461 |
| `--stubbornness 0.2` | 0.212 | 0.377 |
| `--stubbornness 0.05` | 0.145 | 0.620 |

Under the engagement feed a narrow `--epsilon` lowers the spread instead, because content `--feed_push` away from the viewer is then often out of reach.

## The feed
Recommendation algorithms act on *exposure*: they choose what people see, and that content competes with what people hear from friends.
`--lambda_` is therefore the share of each agent's attention that goes to the feed; the remaining `1 - lambda_` goes to the peer network.
Every day each agent sees one content item, whose opinion position depends on the feed:

- **Normalizing feed** (`--engagement 0`): mainstream content. Popular posts sit near the population mean, so the item is at the mean opinion plus N(0, `--feed_spread`).
- **Engagement feed** (`--engagement 1`): content from the viewer's own side (the sign of its opinion), `--feed_push` (0.3) more extreme than the viewer, plus N(0, `--feed_spread`), clipped to [-1, 1]. It also carries **outrage** about the other side: every day each viewer's out-group trust falls by `lambda_ · --feed_outrage`, without moving positions (affective rather than ideological polarization).

The item then goes through the same **bounded-confidence** rule as a partner: if it is within `--epsilon` of the viewer's opinion, the viewer moves `lambda_ · feed_influence · trust` of the way toward it, where `trust` is the viewer's in- or out-group trust depending on the item's side. Content further away is ignored.
So people far from the mainstream ignore a normalizing feed, and an engagement feed only ever pulls an agent a bit further along its own side. Agents near the bounds see content at the bound and stop moving.
A day's feed is many posts, so at full attention it moves opinions four times as much as one conversation (`--feed_influence 0.2` vs. `--influence 0.05`).

**Calibration.** Real feed effects are modest: in the 2023 Meta election experiments (Guess et al., *Science*; Nyhan et al., *Nature*) changing people's feeds for about three months produced little measurable change in polarization, and feelings toward the other side have shifted more than policy positions (Iyengar et al. 2019).
This toy **exaggerates the feed for teaching**: at the default 15% attention it moves the spread by about 15% over 150 days, and the larger settings (`--lambda_ 0.5`, half of all attention) are there to make the mechanism easy to see.

Typical results (150 days, mean of the last 50 days over seeds 3, 7, 11, 23, 42, 99; "at bounds" is `extreme_share`, the share of agents with |opinion| ≥ 0.9; "middle" the share with |opinion| < 0.1 at the end; "rise" is how much `opinion_std` grew between days 50–100 and 100–150; "coop." the disaster cooperation at the end):

| run | opinion_std (range over seeds) | rise | at bounds | middle | avg_trust_in | avg_trust_out | coop. | minority_starvation_rate | stability |
|---|---|---|---|---|---|---|---|---|---|
| `--lambda_ 0` (no feed) | 0.570 (0.52–0.61) | +0.07 | 0.21 | 0.16 | 0.639 | 0.550 | 0.54 | 0.544 | 0.535 |
| `--lambda_ 0.15` (default) | 0.484 (0.39–0.59) | +0.08 | 0.15 | 0.22 | 0.639 | 0.554 | 0.54 | 0.548 | 0.535 |
| `--lambda_ 0.5` | 0.315 (0.28–0.39) | +0.04 | 0.05 | 0.38 | 0.636 | 0.549 | 0.54 | 0.552 | 0.535 |
| `--lambda_ 0.15 --engagement 1` | 0.671 (0.61–0.72) | +0.05 | 0.29 | 0.05 | 0.640 | 0.486 | 0.48 | 0.545 | 0.535 |
| `--lambda_ 0.5 --engagement 1` | 0.756 (0.74–0.78) | +0.00 | 0.36 | 0.01 | 0.651 | 0.336 | 0.32 | 0.536 | 0.536 |

The same runs with the outlier groups removed (`sim.affil[:] = "none"` before `run()`), so only peers, the feed and anchoring move opinions:

| run | opinion_std (range over seeds) | settles by (day) | at bounds | middle | anchor corr. | avg_trust_out | coop. |
|---|---|---|---|---|---|---|---|
| `--lambda_ 0` | 0.204 (0.18–0.22) | 50 (39–68) | 0.00 | 0.42 | 0.98 | 0.649 | 0.64 |
| `--lambda_ 0.15` | 0.184 (0.17–0.20) | 40 (33–48) | 0.00 | 0.48 | 0.96 | 0.653 | 0.65 |
| `--lambda_ 0.5` | 0.154 (0.14–0.17) | 32 (19–58) | 0.00 | 0.57 | 0.94 | 0.656 | 0.65 |
| `--lambda_ 0.15 --engagement 1` | 0.286 (0.27–0.30) | 106 (88–150) | 0.00 | 0.16 | 0.96 | 0.571 | 0.56 |
| `--lambda_ 0.5 --engagement 1` | 0.472 (0.45–0.49) | 55 (51–58) | 0.03 | 0.01 | 0.87 | 0.390 | 0.38 |

("settles by" is the first day after which `opinion_std` stays closer to its final level than 10% of its total change.)

What this shows:

- **The engagement feed builds echo chambers, not a society pinned at ±1.** The old engagement mode pushed everyone 15% a day away from the mean and ended with an opinion std of 0.99, nearly everyone at a bound. Now the middle empties out (1% of agents within 0.1 of the center at `--lambda_ 0.5`, against 42% without a feed) and two separated camps form. Without outlier groups only 3% end up at the bounds: mostly agents with almost no stubbornness, which keep following ever more extreme content until there is none left.
- **The normalizing feed's effect on opinion spread is moderate.** 15% attention lowers the spread by about 15%, half of all attention by about 45%. It never produces consensus, because agents far from the mainstream ignore it (bounded confidence) and everyone keeps being pulled back to their anchor.
- **The dial's effect on trust shows up in out-group trust and cooperation.** The engagement feed's outrage lowers out-group trust (0.55 → 0.49 at 15% attention, 0.34 at 50%), while in-group trust is unchanged. That pushes disaster cooperation below the 0.5 threshold, so joint responses fail. The normalizing feed leaves trust where it is.
- **Starvation and stability barely move.** Minority starvation stays at 0.54–0.55 in every setting, within seed noise: the minority's income gap dominates it, and aid mostly flows between like-minded partners anyway.
- **With the outlier groups, the spread is still rising at day 150 in every setting.** The archetypes' `polarization` grows with their membership, and almost everyone joins a group (issue #18). The old dial hid this with a direct 15%-a-day pull toward the mean; the feed does not, so even the default run polarizes (0.48, with 15% of agents at the bounds). The extremes there come from the groups, not the feed.

**Tradeoff kept visible on purpose.** Agents far from the mainstream are easier to recruit into *any* outlier group (`--extremity_susceptibility`), including `social_justice`, whose `policy_push` raises minority income. A normalizing feed therefore also slows the dissent that helps the minority: at `--lambda_ 0.5`, 18% of agents end up in `social_justice` against 21% without a feed. With today's recruitment almost everyone still joins some group, so the effect is small; issue #18 decides how strong it should be.

Trust settles within the run: the last 50 days differ from the 50 before by at most 0.03, and the seeds agree to within ±0.03.
Inequality (about 0.31) and stability are dominated by the gap between majority savings and the minority's hand-to-mouth income in every setting.

## Outputs
- `metrics.csv` with all tracked metrics.
- `metrics_over_time.png` (stability, average/in-group/out-group trust, 1-inequality).
- `diversity_and_minority.png` (minority and majority starvation rates, opinion & affiliation diversity, share of opinions at the bounds).

Metric definitions:
- `minority_starvation_rate` / `majority_starvation_rate`: share of that group whose resources on hand (savings + income + aid) are below `survival_floor`, i.e. who can't cover the day's consumption. `overall_starvation_rate` is the same over everyone. The minority rate is empty (NaN) when `--minority_share 0`.
- `avg_trust_in` / `avg_trust_out`: mean in-group and out-group trust over all agents; `avg_trust` is the mean of the two.
- `disaster_loss`: share of resources on hand destroyed by a disaster that day (0 on days without one); `disaster_cooperation`: the cooperation level of that day's response (empty on days without one).
- `inequality`: Gini coefficient of resources on hand (before consumption).
- `stability` = `1 - 0.7·CV(resources on hand) - 0.3·overall_starvation_rate`, clipped to [0, 1].
- `diversity`: opinions are cut into 10 equal bins over [-1, 1]; Shannon entropy of the bin shares divided by `log2(10)`. 1 means spread evenly over all 10 bins; two equally full bins give 0.30.
- `extreme_share`: share of agents whose opinion is at least 0.9 from the center (|opinion| ≥ 0.9), i.e. at or near the bounds.
- `affil_entropy`: the same over the 6 affiliations (5 archetypes plus `"none"`), divided by `log2(6)`.

## Notes
- This is **not** a real social prediction engine; it’s a **teaching toy** to visualize tradeoffs.
- Everything is modular—tweak `outliers_config.py` and the knobs in `run_cli.py`.
- You can build Primer-style episodes by fixing a few dials and narrating the trajectories.

MIT License.
