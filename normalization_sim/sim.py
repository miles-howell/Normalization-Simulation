
from __future__ import annotations
import numpy as np
import pandas as pd
from collections import Counter
from math import log2
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
from .outliers_config import OUTLIERS

@dataclass
class Params:
    N: int = 240
    share_minority: float = 0.3
    days: int = 120
    base_majority: float = 1.0
    base_minority: float = 0.4          # below survival_floor by design: the minority can't cover its needs without aid
    survival_floor: float = 0.5         # daily consumption; agents with less than this on hand are starving
    resource_decay: float = 0.1         # share of savings lost each day (spoilage/depreciation); 1 = no savings
    # The feed: each agent sees one content item a day and gives it a share lambda_ of its attention
    lambda_: float = 0.15               # share of attention on the feed (0..1); the rest goes to the peer network
    engagement: int = 0                 # 0: normalizing feed (mainstream content), 1: engagement feed (own side, more extreme)
    feed_influence: float = 0.2         # daily share of the way toward feed content at full attention, times trust in its camp
    feed_spread: float = 0.1            # sd of content positions around their target
    feed_push: float = 0.3              # engagement feed: how much more extreme than the viewer the content is
    feed_outrage: float = 0.01          # engagement feed: daily out-group trust loss at full attention
    p_edge: float = 0.06                # connection probability
    shock_sd: float = 0.25              # daily multiplicative (lognormal) resource shock; creates real need
    # Opinion feedback: how strongly opinion distance |o_i - o_j| (0..2) shapes behavior.
    # Setting these four to 0 decouples opinions from the rest of the model.
    homophily: float = 2.0              # neighbor choice weight *= exp(-homophily * distance)
    opinion_altruism: float = 1.0       # giving capacity *= 1 - opinion_altruism * distance/2
    opinion_trust: float = 0.03         # extra trust loss per unit distance when help is refused
    extremity_susceptibility: float = 0.8  # 0..1; infection prob *= (1-w) + w * |o_i - mean| / EXTREMITY_REF
    trust_half: float = 0.05            # giving capacity *= trust / (trust + trust_half); 0 disables
    # Opinions (Friedkin-Johnsen with bounded confidence): agents are pulled toward their own initial view (anchor)
    # and only listen to partners whose opinion is within epsilon of their own
    influence: float = 0.05             # daily share of the way toward the partner's opinion, times the pair's mean trust
    epsilon: float = 0.5                # bounded confidence: partners further apart than this have no influence
    stubbornness: float = 0.1           # mean daily weight s_i on the agent's anchor; s_i ~ N(mean, mean/2) clipped to [0, 1]
    opinion_group_shift: float = 0.0    # initial minority opinions centered at +shift, majority at -shift*m/(1-m) (mean stays 0)
    opinion_noise: float = 0.0          # sd of each agent's daily idiosyncratic opinion drift; 0 = none
    # Trust only moves when someone needs help; it is split into trust in the own opinion camp and the other one
    trust_gain: float = 0.02            # asker's trust gain when its need is fully covered
    trust_loss: float = 0.02            # asker's trust loss when it gets nothing
    trust_reversion: float = 0.02       # share of the gap to the agent's baseline trust closed each day
    # Disasters: a hazard that destroys resources unless both opinion camps work together on the response
    disaster_days: Tuple[int, ...] = () # days on which a disaster strikes (Simulation.trigger_disaster() adds one by hand)
    disaster_severity: float = 0.5      # share of resources on hand destroyed if the response fails
    disaster_threshold: float = 0.5     # cooperation (lowest camp's mean out-group trust) needed for the response to work
    disaster_mitigation: float = 0.75   # share of the damage a working response prevents
    disaster_trust_shift: float = 0.05  # out-group trust gained when the response works, lost when it fails
    seed: Optional[int] = 7

def gini(x):
    x = np.array(x, dtype=float)
    if np.amin(x) < 0:
        x -= np.amin(x)
    mean = np.mean(x)
    if mean == 0:
        return 0.0
    mad = np.abs(np.subtract.outer(x, x)).mean()
    return 0.5 * mad / mean

def entropy(labels, n_categories):
    """Shannon entropy of labels, normalized by log2(n_categories) to [0, 1].

    n_categories is the number of *possible* categories, so 1.0 means spread
    evenly over all of them, not just over the ones that happen to be present.
    """
    if n_categories < 2:
        return 0.0
    c = Counter(labels)
    if len(c) > n_categories:
        raise ValueError(f"{len(c)} distinct labels but n_categories={n_categories}")
    if len(c) <= 1:
        # A single category has zero entropy; return it explicitly so it isn't -0.0
        return 0.0
    total = sum(c.values())
    probs = np.array([v/total for v in c.values()])
    return float(-np.sum(probs * np.log2(probs)) / log2(n_categories))

def starvation_rate(resources, floor, mask=None):
    """Fraction of agents (optionally only those where mask is True) below the survival floor.

    Returns NaN when the selected group is empty (e.g. minority_share=0).
    """
    r = np.asarray(resources) if mask is None else np.asarray(resources)[mask]
    if r.size == 0:
        return float("nan")
    return float((r < floor).mean())

def choose_neighbor(i, candidates, is_minority, affil, cross_pref, opinions=None, homophily=0.0):
    if len(candidates) == 0:
        return None
    same_group = is_minority[candidates] == is_minority[i]
    weights = np.maximum(1.0 + cross_pref * np.where(same_group, -1.0, 1.0), 0.01)
    if opinions is not None and homophily > 0:
        # Homophily: prefer neighbors with similar opinions
        weights *= np.exp(-homophily * np.abs(opinions[candidates] - opinions[i]))
    weights = weights / weights.sum()
    return np.random.choice(candidates, p=weights)

# Mean |o - mean| of the initial N(0, 0.25) opinions; at this spread contagion runs at its configured rate
EXTREMITY_REF = 0.2

# The giver's trust moves this fraction as much as the receiver's when help flows
GIVER_TRUST_SHARE = 0.25

# Opinions in [-1, 1] are binned into this many equal-width bins for the diversity metric
OPINION_BINS = 10
# Agents with |opinion| at least this are counted as being at the bounds
EXTREME_OPINION = 0.9
# Every outlier archetype plus "none"
N_AFFILIATIONS = len(OUTLIERS) + 1

def ideological_fit(opinions, position, width):
    """How well agents at these opinions fit a group standing at position: 1 at position, falling off over width."""
    return np.exp(-0.5 * ((np.asarray(opinions) - position) / width) ** 2)

def join_probabilities(exposure, opinions, susceptibility, outliers):
    """Each agent's chance of joining each archetype today, as an (agents x archetypes) array in the order of outliers.

    exposure[:, k] is the share of the agent's neighbors in archetype k. Archetype k only recruits agents at or above
    its join_threshold (complex contagion), with a daily hazard of infection x fit x susceptibility.
    The agent joins at most one group: it joins any with chance 1 - prod(1 - hazard_k), split between the groups in
    proportion to their hazards. Nothing depends on the order of the archetypes.
    """
    hazard = np.zeros_like(exposure, dtype=float)
    for k, spec in enumerate(outliers.values()):
        fit = ideological_fit(opinions, spec["position"], spec["fit_width"])
        reached = exposure[:, k] >= spec["join_threshold"]
        hazard[:, k] = np.where(reached, np.clip(spec["infection"] * fit * susceptibility, 0, 1), 0.0)
    total = hazard.sum(axis=1)
    p_any = 1.0 - np.prod(1.0 - hazard, axis=1)
    share = np.divide(hazard, total[:, None], out=np.zeros_like(hazard), where=total[:, None] > 0)
    return share * p_any[:, None]

class Simulation:
    def __init__(self, params: Params):
        self.p = params
        if not 0 <= self.p.lambda_ <= 1:
            raise ValueError(f"lambda_ is a share of attention and must be in [0, 1], got {self.p.lambda_}")
        if self.p.seed is not None:
            np.random.seed(self.p.seed)

        N = self.p.N
        self.is_minority = np.zeros(N, dtype=bool)
        self.is_minority[:int(N * self.p.share_minority)] = True
        np.random.shuffle(self.is_minority)

        self.opinions = np.random.normal(0, 0.25, N)
        shift = self.p.opinion_group_shift
        if shift != 0:
            # Opinions line up with economic position: the minority leans to one side, the majority to the other
            share = self.is_minority.mean()
            self.opinions += np.where(self.is_minority, shift, -shift * share / (1 - share) if share < 1 else 0.0)
        self.opinions = self.opinions.clip(-1, 1)
        # Core attitudes are sticky: each agent keeps being pulled back toward its initial opinion
        self.anchors = self.opinions.copy()
        m = self.p.stubbornness
        self.stubbornness = np.clip(np.random.normal(m, m / 2, N), 0, 1)
        self.altruism = np.clip(np.random.normal(0.1, 0.05, N), 0, 0.6)
        # Each agent's generalized trust; trust in each camp starts there and drifts back to it
        self.trust_base = np.clip(np.random.normal(0.6, 0.1, N), 0, 1)
        self.trust_in = self.trust_base.copy()   # trust in agents on the same side of 0 in opinion
        self.trust_out = self.trust_base.copy()  # trust in agents on the other side
        self.affil = np.array(["none"] * N, dtype=object)

        # Random graph
        adj = (np.random.rand(N, N) < self.p.p_edge).astype(int)
        np.fill_diagonal(adj, 0)
        self.adj = np.maximum(adj, adj.T)

        # Seed small groups: groups start as a local cluster, a founder near the group's position
        # and the founder's neighbors closest to that position
        for k, spec in OUTLIERS.items():
            free = np.where(self.affil == "none")[0]
            if len(free) == 0:
                break
            dist = np.abs(self.opinions - spec["position"])
            founder = free[np.argmin(dist[free])]
            neigh = np.where((self.adj[founder] == 1) & (self.affil == "none"))[0]
            members = np.concatenate(([founder], neigh[np.argsort(dist[neigh])][:spec.get("seed_size", 5) - 1]))
            self.affil[members] = k

        self.base_majority = self.p.base_majority
        self.base_minority = self.p.base_minority
        self.public_good_stock = 0.0
        # Savings carried over from previous days (after consumption and decay)
        self.resources = np.zeros(N)

        self.history: Dict[str, list] = {k: [] for k in [
            "day","stability","inequality","diversity","avg_trust","avg_trust_in","avg_trust_out",
            "minority_starvation_rate","majority_starvation_rate",
            "overall_starvation_rate","affil_entropy","mean_opinion",
            "opinion_std","extreme_share","disaster_loss","disaster_cooperation"
        ]}
        self._disaster_pending = False

    def same_camp(self, i, j):
        """True if agents i and j hold opinions on the same side of 0, i.e. are each other's in-group."""
        return (self.opinions[i] >= 0) == (self.opinions[j] >= 0)

    def trust_toward(self, i, j):
        """Agent i's trust in agent j: in-group or out-group trust depending on their opinion camps."""
        return self.trust_in[i] if self.same_camp(i, j) else self.trust_out[i]

    def feed_content(self):
        """Opinion position of the content item each agent sees today.

        The normalizing feed shows mainstream content: popular posts sit near the population mean.
        The engagement feed shows content from the viewer's own side, feed_push more extreme than the viewer.
        """
        N = self.p.N
        noise = np.random.normal(0, self.p.feed_spread, N) if self.p.feed_spread > 0 else np.zeros(N)
        if self.p.engagement > 0:
            side = np.where(self.opinions >= 0, 1.0, -1.0)
            target = self.opinions + self.p.feed_push * side
        else:
            target = np.full(N, self.opinions.mean())
        return np.clip(target + noise, -1, 1)

    def trigger_disaster(self):
        """Make a disaster strike at the start of the next step."""
        self._disaster_pending = True

    def disaster_cooperation(self):
        """How well the camps can respond together: the lowest camp's mean willingness to work with the other.

        An agent's willingness is its out-group trust. The response is only as strong as the less willing camp.
        If everyone is in one camp there is no divide to bridge, so in-group trust is used instead.
        """
        camp = self.opinions >= 0
        if camp.all() or not camp.any():
            return float(self.trust_in.mean())
        return float(min(self.trust_out[camp].mean(), self.trust_out[~camp].mean()))

    def _strike_disaster(self, resources):
        """Destroy part of everyone's resources on hand; returns (share lost, cooperation)."""
        cooperation = self.disaster_cooperation()
        works = cooperation >= self.p.disaster_threshold
        loss = self.p.disaster_severity * (1.0 - self.p.disaster_mitigation if works else 1.0)
        resources *= 1.0 - loss
        # Working together builds trust across the divide; failing together erodes it
        shift = self.p.disaster_trust_shift if works else -self.p.disaster_trust_shift
        self.trust_out = np.clip(self.trust_out + shift, 0, 1)
        return loss, cooperation

    def step(self, day: int):
        N = self.p.N
        # Today's income: base plus public good
        base_maj_today = self.base_majority * (1.0 + self.public_good_stock)
        base_min_today = self.base_minority * (1.0 + self.public_good_stock)
        self.public_good_stock = max(self.public_good_stock * 0.5, 0.0)

        income = np.where(self.is_minority, base_min_today, base_maj_today)
        if self.p.shock_sd > 0:
            # Mean-preserving lognormal shock (good/bad harvest days)
            sd = self.p.shock_sd
            income = income * np.random.lognormal(-0.5 * sd * sd, sd, N)
        gave = np.zeros(N)
        received = np.zeros(N)

        altruism_delta = np.zeros(N)
        trust_delta = np.zeros(N)
        cross_pref = np.zeros(N)
        policy_push = 0.0
        polarization_delta = 0.0
        ingroup_bonus = np.zeros(N)
        public_good_invest = 0.0

        for k, spec in OUTLIERS.items():
            idx = np.where(self.affil == k)[0]
            if len(idx) == 0:
                continue
            altruism_delta[idx] += spec.get("altruism_delta", 0.0)
            trust_delta[idx] += spec.get("trust_delta", 0.0)
            cross_pref[idx] += spec.get("cross_pref", 0.0)
            ingroup_bonus[idx] += spec.get("ingroup_bonus", 0.0)
            policy_push += spec.get("policy_push", 0.0) * (len(idx)/N)
            polarization_delta += spec.get("polarization", 0.0) * (len(idx)/N)
            public_good_invest += spec.get("public_good", 0.0) * (len(idx)/N)

        # Public good
        if public_good_invest > 0:
            invest_rate = min(public_good_invest, 0.2)
            invested = income * invest_rate
            income = income - invested
            self.public_good_stock += invested.mean() * 0.5

        # What each agent has on hand today: savings plus today's income
        resources = self.resources + income

        disaster_loss, disaster_cooperation = 0.0, float("nan")
        if self._disaster_pending or day in self.p.disaster_days:
            self._disaster_pending = False
            disaster_loss, disaster_cooperation = self._strike_disaster(resources)

        effective_altruism = np.clip(self.altruism + altruism_delta, 0, 0.9)

        # One interaction per agent
        for i in range(N):
            neigh = np.where(self.adj[i] == 1)[0]
            j = choose_neighbor(i, neigh, self.is_minority, self.affil, cross_pref[i],
                                self.opinions, self.p.homophily) if len(neigh)>0 else None
            if j is None:
                continue
            in_group = (self.affil[i] != "none" and self.affil[i] == self.affil[j]) or (self.affil[i] == "religious_cult" and self.affil[j] == "religious_cult")
            bonus = ingroup_bonus[i] if in_group else 0.0
            # Opinion distance in [0, 2]
            dist = abs(self.opinions[i] - self.opinions[j])
            same_camp = self.same_camp(i, j)
            # The pair's trust in each other is in-group trust on both sides or out-group trust on both
            trust = self.trust_in if same_camp else self.trust_out
            need = max(self.p.survival_floor - resources[j], 0)
            give_cap = resources[i] * (effective_altruism[i] + bonus)
            give_cap *= max(1.0 - self.p.opinion_altruism * dist / 2.0, 0.0)
            if self.p.trust_half > 0:
                # Agents who have lost trust in others stop sharing
                give_cap *= trust[i] / (trust[i] + self.p.trust_half)
            transfer = min(need, give_cap)
            if transfer > 0:
                resources[i] -= transfer
                resources[j] += transfer
                gave[i] += transfer
                received[j] += transfer
            if need > 0:
                # Trust only moves when help is needed: the asker gains trust by the share of its need
                # that was covered and loses it by the share that was refused; the giver gains a little.
                # Archetypes' trust boosts apply to everyone, their suspicion only to the other camp.
                td_i = trust_delta[i] if (trust_delta[i] > 0 or not same_camp) else 0.0
                td_j = trust_delta[j] if (trust_delta[j] > 0 or not same_camp) else 0.0
                covered = transfer / need
                gain = self.p.trust_gain + td_j
                loss = self.p.trust_loss + self.p.opinion_trust * dist + max(0, -td_j)
                trust[j] = np.clip(trust[j] + covered * gain - (1 - covered) * loss, 0, 1)
                if transfer > 0:
                    trust[i] = np.clip(trust[i] + GIVER_TRUST_SHARE * (self.p.trust_gain + td_i), 0, 1)

        # Trust is a stable trait: it slowly returns to each agent's baseline
        r = self.p.trust_reversion
        self.trust_in += r * (self.trust_base - self.trust_in)
        self.trust_out += r * (self.trust_base - self.trust_out)

        # Policy pushes minority up a bit (and maybe majority down slightly)
        self.base_minority = max(0.2, min(1.2, self.base_minority + policy_push * 0.02))
        self.base_majority = max(0.6, min(1.4, self.base_majority - policy_push * 0.01))

        # Opinion interactions: one partner per agent, chosen like the aid partner, and one feed item. Both go
        # through bounded confidence: sources further away than epsilon are ignored (no repulsion)
        new_op = self.opinions.copy()
        attention = self.p.lambda_
        for i in range(N):
            neigh = np.where(self.adj[i] == 1)[0]
            j = choose_neighbor(i, neigh, self.is_minority, self.affil, cross_pref[i],
                                self.opinions, self.p.homophily)
            if j is None:
                continue
            diff = self.opinions[j] - self.opinions[i]
            if abs(diff) < self.p.epsilon:
                rate = self.p.influence * (self.trust_toward(i, j) + self.trust_toward(j, i)) / 2.0
                new_op[i] += (1.0 - attention) * rate * diff
        if attention > 0:
            content = self.feed_content()
            diff = content - self.opinions
            # Content is weighed with the viewer's trust in the camp it comes from
            same = (content >= 0) == (self.opinions >= 0)
            trust = np.where(same, self.trust_in, self.trust_out)
            heard = np.abs(diff) < self.p.epsilon
            new_op += heard * attention * self.p.feed_influence * trust * diff
            if self.p.engagement > 0 and self.p.feed_outrage > 0:
                # Outrage content about the other side erodes trust in it without moving positions
                self.trust_out = np.clip(self.trust_out - attention * self.p.feed_outrage, 0, 1)

        mean_op = new_op.mean()
        new_op += polarization_delta * (new_op - mean_op)
        # Group polarization: members are pulled toward the position their group stands for
        for k, spec in OUTLIERS.items():
            idx = self.affil == k
            new_op[idx] += spec.get("opinion_pull", 0.0) * (spec["position"] - new_op[idx])
        # Friedkin-Johnsen anchoring: the settled spread comes from how spread out the anchors are
        s = self.stubbornness
        new_op = s * self.anchors + (1 - s) * new_op
        if self.p.opinion_noise > 0:
            # Optional personal experience nudging opinions
            new_op += np.random.normal(0, self.p.opinion_noise, N)
        self.opinions = np.clip(new_op, -1, 1)

        self.update_affiliations()

        # Metrics
        ineq = gini(resources)
        vol = np.std(resources) / (np.mean(resources) + 1e-9)
        floor = self.p.survival_floor
        starvation = starvation_rate(resources, floor)
        minority_starvation = starvation_rate(resources, floor, self.is_minority)
        majority_starvation = starvation_rate(resources, floor, ~self.is_minority)
        # Stability is a society-wide measure, so it uses the overall starvation rate
        stability = float(np.clip(1.0 - 0.7*vol - 0.3*starvation, 0, 1))

        bins = np.clip(((self.opinions + 1) / 2 * OPINION_BINS).astype(int), 0, OPINION_BINS - 1)
        diversity = entropy(bins, OPINION_BINS)
        aff_ent = entropy(self.affil, N_AFFILIATIONS)

        self.history["day"].append(day)
        self.history["stability"].append(stability)
        self.history["inequality"].append(float(ineq))
        self.history["diversity"].append(float(diversity))
        self.history["avg_trust"].append(float((self.trust_in + self.trust_out).mean() / 2))
        self.history["avg_trust_in"].append(float(self.trust_in.mean()))
        self.history["avg_trust_out"].append(float(self.trust_out.mean()))
        self.history["minority_starvation_rate"].append(minority_starvation)
        self.history["majority_starvation_rate"].append(majority_starvation)
        self.history["overall_starvation_rate"].append(starvation)
        self.history["affil_entropy"].append(float(aff_ent))
        self.history["mean_opinion"].append(float(self.opinions.mean()))
        self.history["opinion_std"].append(float(self.opinions.std()))
        self.history["extreme_share"].append(float((np.abs(self.opinions) >= EXTREME_OPINION).mean()))
        self.history["disaster_loss"].append(disaster_loss)
        self.history["disaster_cooperation"].append(disaster_cooperation)

        # Eat, then carry what is left over to tomorrow
        self.resources = np.maximum(resources - self.p.survival_floor, 0.0) * (1.0 - self.p.resource_decay)

    def update_affiliations(self):
        """Joining and leaving outlier groups, from yesterday's memberships.

        Unaffiliated agents join at most one group (see join_probabilities); agents far from the mainstream are
        easier to recruit. Members leave back to "none" with their group's exit_rate; switching groups happens by
        leaving and later joining another.
        """
        N = self.p.N
        names = list(OUTLIERS)
        if not names:
            return
        members = np.stack([self.affil == k for k in names], axis=1).astype(float)
        degree = self.adj.sum(axis=1)
        exposure = np.divide(self.adj @ members, degree[:, None], out=np.zeros_like(members), where=degree[:, None] > 0)
        extremity = np.abs(self.opinions - self.opinions.mean())
        w = self.p.extremity_susceptibility
        susceptibility = (1.0 - w) + w * extremity / EXTREMITY_REF
        probs = join_probabilities(exposure, self.opinions, susceptibility, OUTLIERS)

        new_aff = self.affil.copy()
        free = self.affil == "none"
        # One draw per agent picks the group it joins, if any
        u = np.random.rand(N)
        cum = np.cumsum(probs, axis=1)
        joined = free & (u < cum[:, -1])
        choice = (u[:, None] >= cum).sum(axis=1)
        new_aff[joined] = np.array(names, dtype=object)[choice[joined]]

        # Members who fit their group well (its committed core) leave at half the exit_rate, those who no longer fit
        # at up to 1.5 times it
        exit_rate = np.zeros(N)
        for k, spec in OUTLIERS.items():
            idx = self.affil == k
            fit = ideological_fit(self.opinions[idx], spec["position"], spec["fit_width"])
            exit_rate[idx] = spec["exit_rate"] * (1.5 - fit)
        leaves = ~free & (np.random.rand(N) < exit_rate)
        new_aff[leaves] = "none"
        self.affil = new_aff

    def run(self) -> pd.DataFrame:
        for day in range(self.p.days):
            self.step(day)
        return pd.DataFrame(self.history)
