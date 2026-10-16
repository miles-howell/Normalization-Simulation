import copy

import numpy as np
import pytest

from normalization_sim import sim as sim_module
from normalization_sim.sim import Params, Simulation


@pytest.fixture
def outliers():
    """Edit OUTLIERS for one test and restore it afterwards."""
    saved = copy.deepcopy(sim_module.OUTLIERS)
    yield sim_module.OUTLIERS
    sim_module.OUTLIERS.clear()
    sim_module.OUTLIERS.update(saved)


def isolated(**kw):
    # No edges and no shocks, so each agent's resources follow the bare savings rule
    return Simulation(Params(N=2, share_minority=0.0, p_edge=0.0, shock_sd=0.0, seed=3, **kw))


# --- savings -----------------------------------------------------------------

def test_savings_are_income_minus_consumption_after_decay():
    sim = isolated(base_majority=1.0, survival_floor=0.5, resource_decay=0.1)
    sim.step(0)
    np.testing.assert_allclose(sim.resources, (1.0 - 0.5) * 0.9)


def test_savings_carry_an_agent_through_a_bad_day():
    sim = isolated(base_majority=1.0, survival_floor=0.5, resource_decay=0.1)
    sim.step(0)
    sim.base_majority = 0.2  # income alone is now below the floor
    sim.step(1)
    assert sim.history["overall_starvation_rate"][-1] == 0.0
    np.testing.assert_allclose(sim.resources, (0.45 + 0.2 - 0.5) * 0.9)


def test_savings_never_go_negative():
    sim = isolated(base_majority=1.0, survival_floor=1.5)
    for day in range(3):
        sim.step(day)
        assert (sim.resources == 0).all()
    assert sim.history["overall_starvation_rate"] == [1.0, 1.0, 1.0]


def test_full_decay_keeps_no_savings():
    sim = Simulation(Params(N=60, days=5, seed=3, resource_decay=1.0))
    sim.run()
    assert (sim.resources == 0).all()


def test_majority_builds_savings_in_default_run():
    sim = Simulation(Params(N=60, days=20, seed=3))
    sim.run()
    # Savings are worth several days of income, not reset to zero each day
    assert sim.resources[~sim.is_minority].mean() > 2 * sim.p.base_majority


# --- inequality --------------------------------------------------------------

def test_inequality_rises_as_savings_build():
    df = Simulation(Params(N=120, days=30, seed=3)).run()
    assert df["inequality"].iloc[15:].mean() > df["inequality"].iloc[0] + 0.05


def test_inequality_responds_to_policy(outliers):
    baseline = Simulation(Params(N=120, days=60, seed=3)).run()
    outliers["social_justice"]["policy_push"] = 5.0
    pushed = Simulation(Params(N=120, days=60, seed=3)).run()
    assert pushed["inequality"].tail(15).mean() < baseline["inequality"].tail(15).mean() - 0.1


# --- starvation --------------------------------------------------------------

def minority_starvation(base_minority, shock_sd=0.25):
    rates = [
        Simulation(Params(N=120, days=60, seed=s, base_minority=base_minority, shock_sd=shock_sd))
        .run()["minority_starvation_rate"].tail(30).mean()
        for s in (3, 7)
    ]
    return float(np.mean(rates))


@pytest.mark.parametrize("shock_sd", [0.25, 0.0])
def test_minority_starvation_is_smooth_in_base_minority(shock_sd):
    base = Params().base_minority
    mid = minority_starvation(base, shock_sd)
    assert 0.2 < mid < 0.95  # the minority is short by design, and aid covers part of the gap
    for nudged in (base - 0.01, base + 0.01):
        assert abs(minority_starvation(nudged, shock_sd) - mid) < 0.1
