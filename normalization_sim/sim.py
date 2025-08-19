
from __future__ import annotations
import numpy as np
import pandas as pd
from collections import Counter
from math import log2
from dataclasses import dataclass
from typing import Dict, Any, Optional
from .outliers_config import OUTLIERS

@dataclass
class Params:
    N: int = 240
    share_minority: float = 0.3
    days: int = 120
    base_majority: float = 1.0
    base_minority: float = 0.5
    survival_floor: float = 0.5
    lambda_: float = 0.15               # normalization strength
    engagement: int = 0                 # 0: normalize toward mean, 1: amplify extremes
    p_edge: float = 0.06                # connection probability
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

def entropy(labels):
    c = Counter(labels)
    total = sum(c.values())
    if total <= 0:
        return 0.0
    probs = np.array([v/total for v in c.values() if v > 0])
    if len(probs) == 0:
        return 0.0
    denom = max(log2(len(c)), 1.0)
    return float(-np.sum(probs * np.log2(probs)) / denom)

def choose_neighbor(i, candidates, is_minority, affil, cross_pref):
    if len(candidates) == 0:
        return None
    weights = []
    for j in candidates:
        same_group = (is_minority[i] == is_minority[j])
        w = 1.0 + (cross_pref * (-1 if same_group else +1))
        weights.append(max(w, 0.01))
    weights = np.array(weights, dtype=float)
    weights = weights / weights.sum()
    return np.random.choice(candidates, p=weights)

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
        self.trust = np.clip(np.random.normal(0.6, 0.1, N), 0, 1)
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

        self.history: Dict[str, list] = {k: [] for k in [
            "day","stability","inequality","diversity","avg_trust",
            "minority_starvation_rate","affil_entropy","mean_opinion",
            "opinion_std"
        ]}

    def step(self, day: int):
        N = self.p.N
        # Base resources plus public good
        base_maj_today = self.base_majority * (1.0 + self.public_good_stock)
        base_min_today = self.base_minority * (1.0 + self.public_good_stock)
        self.public_good_stock = max(self.public_good_stock * 0.5, 0.0)

        resources = np.where(self.is_minority, base_min_today, base_maj_today)
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
            invested = resources * invest_rate
            resources -= invested
            self.public_good_stock += invested.mean() * 0.5

        effective_altruism = np.clip(self.altruism + altruism_delta, 0, 0.9)

        # One interaction per agent
        for i in range(N):
            neigh = np.where(self.adj[i] == 1)[0]
            j = choose_neighbor(i, neigh, self.is_minority, self.affil, cross_pref[i]) if len(neigh)>0 else None
            if j is None:
                continue
            in_group = (self.affil[i] != "none" and self.affil[i] == self.affil[j]) or (self.affil[i] == "religious_cult" and self.affil[j] == "religious_cult")
            bonus = ingroup_bonus[i] if in_group else 0.0
            need = max(self.p.survival_floor - resources[j], 0)
            give_cap = resources[i] * (effective_altruism[i] + bonus)
            transfer = min(need, give_cap)
            if transfer > 0:
                resources[i] -= transfer
                resources[j] += transfer
                gave[i] += transfer
                received[j] += transfer
                self.trust[i] = np.clip(self.trust[i] + 0.02 + trust_delta[i], 0, 1)
                self.trust[j] = np.clip(self.trust[j] + 0.02 + trust_delta[j], 0, 1)
            else:
                self.trust[i] = np.clip(self.trust[i] - 0.005 - max(0, -trust_delta[i]), 0, 1)
                self.trust[j] = np.clip(self.trust[j] - 0.005 - max(0, -trust_delta[j]), 0, 1)

        # Policy pushes minority up a bit (and maybe majority down slightly)
        self.base_minority = max(0.2, min(1.2, self.base_minority + policy_push * 0.02))
        self.base_majority = max(0.6, min(1.4, self.base_majority - policy_push * 0.01))

        # Opinion interactions
        new_op = self.opinions.copy()
        for i in range(N):
            neigh = np.where(self.adj[i] == 1)[0]
            if len(neigh) > 0:
                j = np.random.choice(neigh)
                influence = (self.trust[i] + self.trust[j]) / 4.0
                new_op[i] += influence * (self.opinions[j] - self.opinions[i])

        mean_op = new_op.mean()
        new_op += polarization_delta * (new_op - mean_op)
        if self.p.engagement <= 0:
            new_op += -self.p.lambda_ * (new_op - mean_op)
        else:
            new_op += +self.p.lambda_ * (new_op - mean_op)
        self.opinions = np.clip(new_op, -1, 1)

        # Outlier contagion
        new_aff = self.affil.copy()
        for k, spec in OUTLIERS.items():
            p = spec["infection"]
            susceptible = np.where((self.affil == "none") | (np.random.rand(self.p.N) < 0.03))[0]
            for i in susceptible:
                neigh = np.where(self.adj[i] == 1)[0]
                if len(neigh) == 0: 
                    continue
                if np.any(self.affil[neigh] == k) and (np.random.rand() < p):
                    new_aff[i] = k
        self.affil = new_aff

        # Metrics
        ineq = gini(resources)
        vol = np.std(resources) / (np.mean(resources) + 1e-9)
        starvation = (resources < self.p.survival_floor).mean()
        stability = float(np.clip(1.0 - 0.7*vol - 0.3*starvation, 0, 1))

        bins = np.clip(((self.opinions + 1) / 2 * 10).astype(int), 0, 9)
        diversity = entropy(bins)
        aff_ent = entropy(self.affil)

        self.history["day"].append(day)
        self.history["stability"].append(stability)
        self.history["inequality"].append(float(ineq))
        self.history["diversity"].append(float(diversity))
        self.history["avg_trust"].append(float(self.trust.mean()))
        self.history["minority_starvation_rate"].append(float(starvation))
        self.history["affil_entropy"].append(float(aff_ent))
        self.history["mean_opinion"].append(float(self.opinions.mean()))
        self.history["opinion_std"].append(float(self.opinions.std()))

    def run(self) -> pd.DataFrame:
        for day in range(self.p.days):
            self.step(day)
        return pd.DataFrame(self.history)
