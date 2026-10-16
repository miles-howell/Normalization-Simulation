import numpy as np
import pytest

from normalization_sim.sim import Params, Simulation


def pair(opinions, stubbornness=0.0, **kw):
    """Two linked majority agents with no outliers, shocks or dial, so only peer influence and anchoring move opinions.

    Nobody needs help, so trust stays at its baseline. Both opinions are also the agents' anchors.
    """
    params = dict(N=2, share_minority=0.0, p_edge=1.0, shock_sd=0.0, lambda_=0.0, seed=3)
    params.update(kw)
    sim = Simulation(Params(**params))
    sim.affil[:] = "none"
    sim.opinions[:] = opinions
    sim.anchors[:] = opinions
    sim.stubbornness[:] = stubbornness
    return sim


def test_partner_within_epsilon_pulls_by_influence_times_mean_trust():
    sim = pair((0.1, 0.3))
    rate = sim.p.influence * (sim.trust_in[0] + sim.trust_in[1]) / 2
    sim.step(0)
    np.testing.assert_allclose(sim.opinions, [0.1 + rate * 0.2, 0.3 - rate * 0.2])


def test_partner_beyond_epsilon_has_no_influence_and_no_repulsion():
    sim = pair((-0.4, 0.4))
    sim.step(0)
    np.testing.assert_array_equal(sim.opinions, [-0.4, 0.4])


def test_fully_stubborn_agents_return_to_their_anchors():
    sim = pair((0.1, 0.3), stubbornness=1.0)
    sim.opinions[:] = (0.25, 0.15)
    sim.step(0)
    np.testing.assert_allclose(sim.opinions, [0.1, 0.3])


def test_anchoring_mixes_anchor_and_social_update():
    sim = pair((0.1, 0.3), stubbornness=0.3, epsilon=0.01)  # no peer influence, only the anchor pull
    sim.opinions[:] = (0.5, 0.5)
    sim.step(0)
    np.testing.assert_allclose(sim.opinions, [0.3 * 0.1 + 0.7 * 0.5, 0.3 * 0.3 + 0.7 * 0.5])


def test_stubbornness_is_drawn_around_its_mean():
    sim = Simulation(Params(N=2000, stubbornness=0.1, seed=3))
    assert sim.stubbornness.min() >= 0
    assert sim.stubbornness.mean() == pytest.approx(0.1, abs=0.005)
    np.testing.assert_array_equal(sim.anchors, sim.opinions)


# --- whole runs ----------------------------------------------------------------

def without_groups(**kw):
    """A run with no outlier groups, so only peers, the feed and anchoring move opinions."""
    sim = Simulation(Params(**{"N": 120, "days": 150, **kw}))
    sim.affil[:] = "none"
    return sim


def settled_std(**kw):
    """Opinion spread over the last 50 days without outlier groups, averaged over two seeds."""
    return float(np.mean([without_groups(seed=s, **kw).run()["opinion_std"].tail(50).mean() for s in (3, 7)]))


def test_default_spread_settles_above_zero_and_agents_keep_their_views():
    sim = without_groups(seed=7)
    std = sim.run()["opinion_std"]
    settled = std.tail(50).mean()
    assert settled > 0.05
    # Settled: the last 50 days barely differ from the 50 before
    assert abs(settled - std.iloc[-100:-50].mean()) < 0.01
    assert np.corrcoef(sim.anchors, sim.opinions)[0, 1] > 0.8


def test_peer_influence_alone_settles_over_weeks():
    # No dial and no outlier groups: only peer influence and anchoring move opinions
    sim = without_groups(seed=7, lambda_=0.0)
    std = sim.run()["opinion_std"]
    settled = std.tail(50).mean()
    assert settled > 0.1
    assert abs(settled - std.iloc[-100:-50].mean()) < 0.01
    # Still well short of its settled level after two weeks
    assert std.iloc[14] - settled > 0.3 * (std.iloc[0] - settled)
    assert np.corrcoef(sim.anchors, sim.opinions)[0, 1] > 0.9


def test_wider_confidence_narrows_the_spread():
    assert settled_std(epsilon=1.0) < settled_std(epsilon=0.25)


def test_less_stubbornness_narrows_the_spread():
    assert settled_std(stubbornness=0.05) < settled_std(stubbornness=0.2)


def test_group_shift_leans_the_minority_one_way_and_keeps_the_mean():
    sim = Simulation(Params(N=2000, opinion_group_shift=0.3, seed=5))
    mino = sim.is_minority
    assert sim.opinions[mino].mean() == pytest.approx(0.3, abs=0.03)
    assert sim.opinions[~mino].mean() == pytest.approx(-0.3 * 0.3 / 0.7, abs=0.03)
    assert sim.opinions.mean() == pytest.approx(0.0, abs=0.02)
    assert np.array_equal(sim.anchors, sim.opinions)


def test_zero_group_shift_leaves_initial_opinions_unchanged():
    a = Simulation(Params(seed=11))
    b = Simulation(Params(seed=11, opinion_group_shift=0.0))
    assert np.array_equal(a.opinions, b.opinions)
