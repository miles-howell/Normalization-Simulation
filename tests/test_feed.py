import numpy as np
import pytest

from normalization_sim.sim import Params, Simulation


def pair(opinions, **kw):
    """Two linked majority agents with no outliers, shocks or anchoring, giving all their attention to the feed.

    Nobody needs help, so trust only moves through the feed. Feed content sits exactly on its target.
    """
    params = dict(N=2, share_minority=0.0, p_edge=1.0, shock_sd=0.0, lambda_=1.0, feed_spread=0.0, seed=3)
    params.update(kw)
    sim = Simulation(Params(**params))
    sim.affil[:] = "none"
    sim.opinions[:] = opinions
    sim.anchors[:] = opinions
    sim.stubbornness[:] = 0.0
    return sim


def test_lambda_is_a_share_of_attention():
    with pytest.raises(ValueError):
        Simulation(Params(N=10, lambda_=1.5))


def test_normalizing_feed_shows_mainstream_content():
    sim = pair((0.1, 0.3))
    np.testing.assert_allclose(sim.feed_content(), [0.2, 0.2])


def test_engagement_feed_shows_more_extreme_content_from_the_viewers_side():
    sim = pair((-0.2, 0.9), engagement=1, feed_push=0.3)
    np.testing.assert_allclose(sim.feed_content(), [-0.5, 1.0])  # clipped at the bound


def test_feed_pulls_by_attention_times_influence_times_trust():
    sim = pair((0.1, 0.3), lambda_=0.5)
    # Partners pull with the other half of the attention; content and partner are both on the same side
    peer = 0.5 * sim.p.influence * (sim.trust_in[0] + sim.trust_in[1]) / 2 * 0.2
    feed = 0.5 * sim.p.feed_influence * sim.trust_in * np.array([0.1, -0.1])
    sim.step(0)
    np.testing.assert_allclose(sim.opinions, [0.1 + peer + feed[0], 0.3 - peer + feed[1]])


def test_feed_content_beyond_epsilon_is_ignored():
    sim = pair((-0.4, 0.4), epsilon=0.3)  # mainstream content at 0 is 0.4 away from both
    sim.step(0)
    np.testing.assert_array_equal(sim.opinions, [-0.4, 0.4])


def test_engagement_feed_erodes_out_group_trust_only():
    sim = pair((0.1, 0.3), engagement=1, lambda_=0.5, feed_outrage=0.02)
    base = sim.trust_base.copy()
    sim.step(0)
    np.testing.assert_allclose(sim.trust_out, base - 0.5 * 0.02)
    np.testing.assert_allclose(sim.trust_in, base)


# --- whole runs ----------------------------------------------------------------

def final(seed=7, groups=True, **kw):
    sim = Simulation(Params(N=120, days=150, seed=seed, **kw))
    if not groups:
        sim.affil[:] = "none"
    return sim, sim.run().tail(50).mean(numeric_only=True)


@pytest.mark.parametrize("seed", [3, 7])
def test_normalizing_feed_narrows_the_spread_moderately(seed):
    _, off = final(seed, lambda_=0.0)
    _, on = final(seed, lambda_=0.5)
    assert 0.3 * off.opinion_std < on.opinion_std < 0.9 * off.opinion_std


@pytest.mark.parametrize("seed", [3, 7])
def test_engagement_feed_splits_opinions_into_separated_clusters(seed):
    # Without outlier groups only peers, anchors and the feed move opinions
    sim, _ = final(seed, groups=False, lambda_=0.5, engagement=1)
    o = sim.opinions
    # Two camps of similar size whose centers are far apart, with a thin middle and few agents at the bounds
    assert 0.3 < (o >= 0).mean() < 0.7
    assert o[o >= 0].mean() - o[o < 0].mean() > 0.6
    assert (np.abs(o) < 0.1).mean() < 0.15
    assert (np.abs(o) >= 0.9).mean() < 0.1


@pytest.mark.parametrize("seed", [3, 7])
def test_engagement_feed_widens_the_spread_without_pinning_everyone_at_the_bounds(seed):
    _, off = final(seed, lambda_=0.0)
    _, on = final(seed, lambda_=0.15, engagement=1)
    assert on.opinion_std > off.opinion_std
    assert on.extreme_share < 0.5


def test_engagement_feed_lowers_out_group_trust_and_cooperation():
    norm, n = final(lambda_=0.5)
    eng, e = final(lambda_=0.5, engagement=1)
    assert e.avg_trust_out < n.avg_trust_out - 0.1
    assert abs(e.avg_trust_in - n.avg_trust_in) < 0.05
    assert eng.disaster_cooperation() < norm.disaster_cooperation()
