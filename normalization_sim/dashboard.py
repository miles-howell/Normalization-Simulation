"""Non-UI helpers for the Streamlit app (app.py): parameter controls, recorded runs and derived views."""
from __future__ import annotations
import threading
from dataclasses import dataclass, fields, replace
from typing import Callable, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from .sim import Params, Simulation
from .outliers_config import OUTLIERS


@dataclass(frozen=True)
class Control:
    field: str
    label: str
    lo: float
    hi: float
    step: float
    help: str = ""
    kind: str = "slider"  # slider, int, toggle or days


# Sidebar controls, grouped like the README sections. Ranges are what the UI allows, not hard model limits.
CONTROL_GROUPS: Dict[str, List[Control]] = {
    "Feed": [
        Control("lambda_", "Attention on the feed (lambda)", 0.0, 1.0, 0.01,
                "Share of attention on the algorithmic feed; the rest goes to peers"),
        Control("engagement", "Engagement-optimized feed", 0, 1, 1,
                "Off: mainstream (normalizing) content. On: own side, more extreme, plus outrage", kind="toggle"),
        Control("feed_influence", "Feed influence", 0.0, 1.0, 0.01,
                "Daily share of the way toward feed content at full attention, times trust"),
        Control("feed_spread", "Feed spread", 0.0, 0.5, 0.01, "sd of feed content positions around their target"),
        Control("feed_push", "Engagement push", 0.0, 1.0, 0.01,
                "Engagement feed: how much more extreme than the viewer content is"),
        Control("feed_outrage", "Engagement outrage", 0.0, 0.1, 0.001,
                "Engagement feed: daily out-group trust loss at full attention"),
    ],
    "Population & economy": [
        Control("N", "Agents", 20, 600, 20, "Number of agents; runtime grows with it", kind="int"),
        Control("share_minority", "Minority share", 0.0, 1.0, 0.01),
        Control("base_majority", "Majority income", 0.0, 2.0, 0.05),
        Control("base_minority", "Minority income", 0.0, 2.0, 0.05),
        Control("survival_floor", "Survival floor", 0.0, 2.0, 0.05,
                "Daily consumption; less than this on hand = starving"),
        Control("resource_decay", "Resource decay", 0.0, 1.0, 0.01, "Share of savings lost each day; 1 = no savings"),
        Control("shock_sd", "Income shock sd", 0.0, 1.0, 0.01, "Daily lognormal resource shock; 0 = none"),
        Control("p_edge", "Connection probability", 0.01, 0.3, 0.01),
    ],
    "Opinions": [
        Control("influence", "Peer influence", 0.0, 0.5, 0.01,
                "Daily share of the way toward a partner's opinion, times the pair's mean trust"),
        Control("epsilon", "Bounded confidence (epsilon)", 0.0, 2.0, 0.05,
                "Partners further apart in opinion than this have no influence"),
        Control("stubbornness", "Stubbornness", 0.0, 1.0, 0.01, "Mean daily pull back toward each agent's initial view"),
        Control("opinion_noise", "Opinion noise", 0.0, 0.2, 0.005, "Daily personal opinion drift (sd)"),
        Control("homophily", "Homophily", 0.0, 10.0, 0.1, "Preference for like-minded partners"),
        Control("opinion_altruism", "Opinion altruism", 0.0, 2.0, 0.05, "How much opinion distance cuts giving"),
        Control("extremity_susceptibility", "Extremity susceptibility", 0.0, 1.0, 0.01,
                "How much distance from the mean drives outlier recruitment"),
    ],
    "Trust": [
        Control("trust_gain", "Trust gain", 0.0, 0.2, 0.005, "Asker's trust gain when its need is fully covered"),
        Control("trust_loss", "Trust loss", 0.0, 0.2, 0.005, "Asker's trust loss when it gets no help"),
        Control("trust_reversion", "Trust reversion", 0.0, 0.2, 0.005, "Share of the gap to baseline closed each day"),
        Control("opinion_trust", "Opinion trust", 0.0, 0.2, 0.005,
                "Extra trust loss per unit opinion distance when help is refused"),
        Control("trust_half", "Trust half", 0.0, 0.5, 0.01, "Trust at which giving is halved; 0 = trust doesn't gate giving"),
    ],
    "Disasters": [
        Control("disaster_days", "Disaster days", 0, 0, 0, "Days on which a disaster strikes, e.g. 60 100", kind="days"),
        Control("disaster_severity", "Severity", 0.0, 1.0, 0.01, "Share of resources destroyed if the response fails"),
        Control("disaster_threshold", "Cooperation threshold", 0.0, 1.0, 0.01,
                "Lowest camp's mean out-group trust the response needs"),
        Control("disaster_mitigation", "Mitigation", 0.0, 1.0, 0.01, "Share of the damage a working response prevents"),
        Control("disaster_trust_shift", "Trust shift", 0.0, 0.2, 0.005,
                "Out-group trust gained/lost when the response works/fails"),
    ],
    "Run": [
        Control("days", "Days", 10, 500, 10, kind="int"),
        Control("seed", "Seed", 0, 10_000, 1, kind="int"),
    ],
}

CONTROLS: Dict[str, Control] = {c.field: c for group in CONTROL_GROUPS.values() for c in group}

PRESETS: Dict[str, Dict] = {
    "Normalizing feed (default)": {},
    "Engagement feed": {"engagement": 1},
    "Heavy feed use": {"lambda_": 0.5},
    "Engagement feed + disasters": {"engagement": 1, "lambda_": 0.3, "disaster_days": (60, 100)},
    "Echo chambers": {"homophily": 6.0, "epsilon": 0.3},
}


def parse_days(text: str) -> Tuple[int, ...]:
    """'60 100' or '60, 100' -> (60, 100); raises ValueError on anything else."""
    parts = text.replace(",", " ").split()
    days = tuple(sorted({int(p) for p in parts}))
    if any(d < 0 for d in days):
        raise ValueError("disaster days must be non-negative")
    return days


def format_days(days: Tuple[int, ...]) -> str:
    return " ".join(str(d) for d in days)


def preset_params(name: str) -> Params:
    return replace(Params(days=150), **PRESETS[name])


def params_key(p: Params) -> tuple:
    """Hashable identity of a parameter set (Params itself is mutable and unhashable)."""
    return tuple(getattr(p, f.name) for f in fields(p))


@dataclass
class RunResult:
    params: Params
    metrics: pd.DataFrame
    opinions: np.ndarray      # (days, N) after each day
    resources: np.ndarray     # (days, N) savings carried over after each day
    affil: np.ndarray         # (days, N) affiliation labels after each day
    is_minority: np.ndarray   # (N,)
    adj: np.ndarray           # (N, N) network


# Simulation seeds and draws from numpy's global RNG, so concurrent runs (e.g. two browser tabs) would
# interleave draws and stop being reproducible. Run one at a time.
_RUN_LOCK = threading.Lock()


def run_recorded(p: Params, on_day: Optional[Callable[[int], None]] = None) -> RunResult:
    """Run a simulation, keeping per-agent state for every day. on_day(day) is called after each day."""
    with _RUN_LOCK:
        sim = Simulation(p)
        snaps = []
        for day in sim.iter_days():
            snaps.append(sim.snapshot())
            if on_day is not None:
                on_day(day)
    stack = lambda key: np.array([s[key] for s in snaps])
    return RunResult(
        params=p, metrics=pd.DataFrame(sim.history), opinions=stack("opinions"), resources=stack("resources"),
        affil=stack("affil"), is_minority=sim.is_minority.copy(), adj=sim.adj.copy(),
    )


def opinion_density(opinions: np.ndarray, bins: int = 40) -> Tuple[np.ndarray, np.ndarray]:
    """Share of agents in each opinion bin per day: returns (bin centers, (bins, days) array)."""
    edges = np.linspace(-1, 1, bins + 1)
    counts = np.array([np.histogram(day, bins=edges)[0] for day in opinions]).T
    return (edges[:-1] + edges[1:]) / 2, counts / opinions.shape[1]


def affiliation_shares(affil: np.ndarray) -> pd.DataFrame:
    """Share of agents in each outlier group per day (columns in OUTLIERS order, then 'none')."""
    names = list(OUTLIERS) + ["none"]
    return pd.DataFrame({k: (affil == k).mean(axis=1) for k in names})


def summarize(metrics: pd.DataFrame, last: int = 30) -> pd.Series:
    """Mean of each metric over the last `last` days: the run's settled outcome."""
    cols = [c for c in metrics.columns if c not in ("day", "disaster_loss", "disaster_cooperation")]
    return metrics[cols].tail(last).mean()
