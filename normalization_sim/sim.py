
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
    lambda_: float = 0.15               # normalization strength
    engagement: int = 0                 # 0: normalize toward mean, 1: amplify extremes
    p_edge: float = 0.06                # connection probability
    shock_sd: float = 0.25              # daily multiplicative (lognormal) resource shock; creates real need
    # Opinion feedback: how strongly opinion distance |o_i - o_j| (0..2) shapes behavior.
    # Setting these four to 0 decouples opinions from the rest of the model.
    homophily: float = 2.0              # neighbor choice weight *= exp(-homophily * distance)
    opinion_altruism: float = 1.0       # giving capacity *= 1 - opinion_altruism * distance/2
    opinion_trust: float = 0.03         # extra trust loss per unit distance when help is refused
    extremity_susceptibility: float = 0.8  # 0..1; infection prob *= (1-w) + w * |o_i - mean| / EXTREMITY_REF
    trust_half: float = 0.05            # giving capacity *= trust / (trust + trust_half); 0 disables
    opinion_noise: float = 0.03         # sd of each agent's daily idiosyncratic opinion drift
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
    weights = []
    for j in candidates:
        same_group = (is_minority[i] == is_minority[j])
        w = 1.0 + (cross_pref * (-1 if same_group else +1))
        weights.append(max(w, 0.01))
    weights = np.array(weights, dtype=float)
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
# Every outlier archetype plus "none"
N_AFFILIATIONS = len(OUTLIERS) + 1

class Simulation:
    def __init__(self, params: Params):
        self.p = params
        if self.p.seed is not None:
            np.random.seed(self.p.seed)

        N = self.p.N
        self.is_minority = np.zeros(N, dtype=bool)
        self.is_minority[:int(N * self.p.share_minority)] = True
        np.random.shuffle(self.is_minority)

        self.opinions = np.random.normal(0, 0.25, N).clip(-1, 1)
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

        # Seed small groups
        seeds = {"social_justice": 6, "political_extremists": 6, "environmentalists": 5, "antivaxx_misinfo": 5, "religious_cult": 5}
        idxs = np.random.permutation(N)
        cursor = 0
        for k, cnt in seeds.items():
            self.affil[idxs[cursor:cursor+cnt]] = k
            cursor += cnt

        self.base_majority = self.p.base_majority
        self.base_minority = self.p.base_minority
        self.public_good_stock = 0.0
        # Savings carried over from previous days (after consumption and decay)
        self.resources = np.zeros(N)

        self.history: Dict[str, list] = {k: [] for k in [
            "day","stability","inequality","diversity","avg_trust","avg_trust_in","avg_trust_out",
            "minority_starvation_rate","majority_starvation_rate",
            "overall_starvation_rate","affil_entropy","mean_opinion",
            "opinion_std","disaster_loss","disaster_cooperation"
        ]}
        self._disaster_pending = False

    def same_camp(self, i, j):
        """True if agents i and j hold opinions on the same side of 0, i.e. are each other's in-group."""
        return (self.opinions[i] >= 0) == (self.opinions[j] >= 0)

    def trust_toward(self, i, j):
        """Agent i's trust in agent j: in-group or out-group trust depending on their opinion camps."""
        return self.trust_in[i] if self.same_camp(i, j) else self.trust_out[i]

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

        # Opinion interactions
        new_op = self.opinions.copy()
        for i in range(N):
            neigh = np.where(self.adj[i] == 1)[0]
            if len(neigh) > 0:
                j = np.random.choice(neigh)
                influence = (self.trust_toward(i, j) + self.trust_toward(j, i)) / 4.0
                new_op[i] += influence * (self.opinions[j] - self.opinions[i])

        mean_op = new_op.mean()
        new_op += polarization_delta * (new_op - mean_op)
        if self.p.engagement <= 0:
            new_op += -self.p.lambda_ * (new_op - mean_op)
        else:
            new_op += +self.p.lambda_ * (new_op - mean_op)
        if self.p.opinion_noise > 0:
            # Personal experience keeps nudging opinions, so spread settles where noise balances the pull to consensus
            new_op += np.random.normal(0, self.p.opinion_noise, N)
        self.opinions = np.clip(new_op, -1, 1)

        # Outlier contagion: agents far from the mainstream are more susceptible
        new_aff = self.affil.copy()
        extremity = np.abs(self.opinions - self.opinions.mean())
        w = self.p.extremity_susceptibility
        susceptibility = (1.0 - w) + w * extremity / EXTREMITY_REF
        for k, spec in OUTLIERS.items():
            p = spec["infection"]
            susceptible = np.where((self.affil == "none") | (np.random.rand(self.p.N) < 0.03))[0]
            for i in susceptible:
                neigh = np.where(self.adj[i] == 1)[0]
                if len(neigh) == 0: 
                    continue
                if np.any(self.affil[neigh] == k) and (np.random.rand() < p * susceptibility[i]):
                    new_aff[i] = k
        self.affil = new_aff

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
        self.history["disaster_loss"].append(disaster_loss)
        self.history["disaster_cooperation"].append(disaster_cooperation)

        # Eat, then carry what is left over to tomorrow
        self.resources = np.maximum(resources - self.p.survival_floor, 0.0) * (1.0 - self.p.resource_decay)

    def run(self) -> pd.DataFrame:
        for day in range(self.p.days):
            self.step(day)
        return pd.DataFrame(self.history)
