import copy

import numpy as np
import pytest

from normalization_sim import sim as sim_module
from normalization_sim.sim import Params, Simulation, ideological_fit, join_probabilities


@pytest.fixture
def outliers():
    """Edit OUTLIERS for one test and restore it afterwards."""
    saved = copy.deepcopy(sim_module.OUTLIERS)
    yield sim_module.OUTLIERS
    sim_module.OUTLIERS.clear()
    sim_module.OUTLIERS.update(saved)


def group(**kw):
    spec = dict(join_threshold=0.1, infection=0.5, position=0.0, fit_width=0.25, exit_rate=0.0, opinion_pull=0.0)
    spec.update(kw)
    return spec


# --- join_probabilities --------------------------------------------------------

def test_no_join_below_the_threshold():
    groups = {"a": group(join_threshold=0.2)}
    probs = join_probabilities(np.array([[0.19], [0.2]]), np.zeros(2), np.ones(2), groups)
    assert probs[0, 0] == 0.0
    assert probs[1, 0] == pytest.approx(0.5)


def test_join_chance_falls_with_ideological_distance():
    groups = {"a": group(position=0.5)}
    probs = join_probabilities(np.ones((3, 1)), np.array([0.5, 0.25, -0.5]), np.ones(3), groups)[:, 0]
    assert probs[0] > probs[1] > probs[2]
    np.testing.assert_allclose(probs, 0.5 * ideological_fit([0.5, 0.25, -0.5], 0.5, 0.25))


def test_agent_joins_at_most_one_group():
    groups = {"a": group(infection=0.6), "b": group(infection=0.3)}
    probs = join_probabilities(np.ones((1, 2)), np.zeros(1), np.ones(1), groups)[0]
    assert probs.sum() == pytest.approx(1 - 0.4 * 0.7)
    assert probs[0] / probs[1] == pytest.approx(2.0)


def test_join_probabilities_do_not_depend_on_archetype_order():
    rng = np.random.default_rng(0)
    groups = {"a": group(position=-0.3, infection=0.2), "b": group(position=0.1, join_threshold=0.05),
              "c": group(position=0.4, infection=0.9, fit_width=0.1)}
    exposure = rng.random((50, 3)) * 0.3
    opinions = rng.uniform(-1, 1, 50)
    probs = join_probabilities(exposure, opinions, np.ones(50), groups)
    order = ["c", "a", "b"]
    reordered = {k: groups[k] for k in order}
    cols = [list(groups).index(k) for k in order]
    np.testing.assert_allclose(join_probabilities(exposure[:, cols], opinions, np.ones(50), reordered), probs[:, cols])


# --- update_affiliations -------------------------------------------------------

def star(outliers, n=8, **kw):
    """Agent 0 linked to everyone else; the archetypes are replaced by the given groups. Susceptibility is 1."""
    outliers.clear()
    outliers.update(kw)
    sim = Simulation(Params(N=n, share_minority=0.0, p_edge=0.0, extremity_susceptibility=0.0, seed=3))
    sim.adj[0, 1:] = sim.adj[1:, 0] = 1
    sim.affil[:] = "none"
    sim.opinions[:] = 0.0
    return sim


def test_one_contact_is_not_enough_for_a_high_threshold_group(outliers):
    sim = star(outliers, a=group(infection=1.0, join_threshold=0.25))
    sim.affil[1] = "a"  # 1 of agent 0's 7 neighbors
    for _ in range(20):
        sim.update_affiliations()
    assert sim.affil[0] == "none"
    sim.affil[1:3] = "a"  # 2 of 7
    sim.update_affiliations()
    assert sim.affil[0] == "a"


def test_identical_groups_recruit_equally_whatever_their_order(outliers):
    joined = {"a": 0, "b": 0}
    for seed in range(400):
        sim = star(outliers, a=group(infection=0.5), b=group(infection=0.5))
        np.random.seed(seed)
        sim.affil[1:4] = "a"
        sim.affil[4:7] = "b"
        sim.update_affiliations()
        if sim.affil[0] != "none":
            joined[sim.affil[0]] += 1
    assert joined["a"] + joined["b"] > 250
    assert abs(joined["a"] - joined["b"]) < 0.15 * (joined["a"] + joined["b"])


def test_members_leave_at_the_exit_rate_and_do_not_switch_directly(outliers):
    # Fully fitting members leave at half the exit_rate
    sim = star(outliers, n=2000, a=group(infection=1.0, exit_rate=0.2), b=group(infection=1.0, join_threshold=0.0))
    sim.affil[:] = "a"
    sim.update_affiliations()
    assert set(sim.affil) == {"a", "none"}
    assert (sim.affil == "none").mean() == pytest.approx(0.1, abs=0.02)


def test_members_who_no_longer_fit_leave_sooner(outliers):
    sim = star(outliers, n=4000, a=group(exit_rate=0.2, position=0.0, fit_width=0.1))
    sim.affil[:] = "a"
    sim.opinions[2000:] = 1.0  # fit ~ 0
    sim.update_affiliations()
    assert (sim.affil[:2000] == "none").mean() == pytest.approx(0.1, abs=0.02)
    assert (sim.affil[2000:] == "none").mean() == pytest.approx(0.3, abs=0.03)


def test_membership_pulls_opinions_toward_the_group_position(outliers):
    outliers.clear()
    outliers["a"] = group(position=0.8, opinion_pull=0.1, polarization=0.0)
    sim = Simulation(Params(N=2, share_minority=0.0, p_edge=0.0, shock_sd=0.0, lambda_=0.0, seed=3))
    sim.opinions[:] = sim.anchors[:] = 0.0
    sim.stubbornness[:] = 0.0
    sim.affil[:] = ["a", "none"]
    sim.step(0)
    assert sim.opinions[0] == pytest.approx(0.08)
    assert sim.opinions[1] == 0.0


def test_groups_start_as_a_cluster_near_their_position():
    sim = Simulation(Params(seed=7))
    for k, spec in sim_module.OUTLIERS.items():
        members = np.where(sim.affil == k)[0]
        assert len(members) == spec["seed_size"]
        founder = members[np.argmin(np.abs(sim.opinions[members] - spec["position"]))]
        assert all(sim.adj[founder, m] for m in members if m != founder)


# --- whole runs ----------------------------------------------------------------

@pytest.mark.parametrize("seed", [1, 7, 42])
def test_membership_settles_well_short_of_everyone(seed):
    sim = Simulation(Params(N=240, days=150, seed=seed))
    shares = []
    for day in range(150):
        sim.step(day)
        shares.append((sim.affil != "none").mean())
    shares = np.array(shares)
    assert 0.1 < shares[-50:].mean() < 0.6
    # Settled: the last 50 days barely differ from the 50 before
    assert abs(shares[-50:].mean() - shares[-100:-50].mean()) < 0.1


def test_opinion_position_predicts_which_group_an_agent_joins():
    # Initial opinions (anchors) of members are ordered like the groups' positions, so recruitment, not
    # only the pull of membership, sorts agents into groups
    by_group = {k: [] for k in sim_module.OUTLIERS}
    for seed in (1, 7, 42):
        sim = Simulation(Params(N=240, days=150, seed=seed))
        sim.run()
        for k in by_group:
            by_group[k].extend(sim.anchors[sim.affil == k])
    present = [k for k in by_group if len(by_group[k]) >= 10]
    assert len(present) >= 3
    positions = [sim_module.OUTLIERS[k]["position"] for k in present]
    means = [np.mean(by_group[k]) for k in present]
    assert np.corrcoef(positions, means)[0, 1] > 0.9
