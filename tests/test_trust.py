import numpy as np
import pytest

from normalization_sim.sim import GIVER_TRUST_SHARE, Params, Simulation


def pair(altruism, opinions=(0.2, 0.2), **kw):
    """One majority and one minority agent linked to each other, with no outliers, shocks or reversion.

    The majority agent never needs help; the minority agent earns 0.4 against a 0.5 floor, so it asks
    for 0.1 each day. Returns the simulation and the (majority, minority) indices.
    """
    params = dict(N=2, share_minority=0.5, p_edge=1.0, shock_sd=0.0, opinion_noise=0.0,
                  trust_reversion=0.0, seed=3)
    params.update(kw)
    sim = Simulation(Params(**params))
    sim.affil[:] = "none"
    sim.altruism[:] = altruism
    maj, mnr = np.argmin(sim.is_minority), np.argmax(sim.is_minority)
    sim.opinions[maj], sim.opinions[mnr] = opinions
    return sim, maj, mnr


def test_no_trust_change_when_nobody_needs_help():
    sim, _, _ = pair(altruism=0.0, base_minority=1.0)
    before = sim.trust_base.copy()
    sim.step(0)
    np.testing.assert_array_equal(sim.trust_in, before)
    np.testing.assert_array_equal(sim.trust_out, before)


def test_refusal_lowers_only_the_askers_trust():
    sim, maj, mnr = pair(altruism=0.0)
    base = sim.trust_base.copy()
    sim.step(0)
    assert sim.trust_in[mnr] == pytest.approx(base[mnr] - sim.p.trust_loss)
    assert sim.trust_in[maj] == base[maj]
    np.testing.assert_array_equal(sim.trust_out, base)


def test_refusal_across_camps_lowers_out_group_trust_with_opinion_distance():
    sim, maj, mnr = pair(altruism=0.0, opinions=(0.3, -0.3))
    base = sim.trust_base.copy()
    sim.step(0)
    assert sim.trust_out[mnr] == pytest.approx(base[mnr] - sim.p.trust_loss - sim.p.opinion_trust * 0.6)
    np.testing.assert_array_equal(sim.trust_in, base)


def test_help_raises_receivers_trust_and_givers_a_little():
    sim, maj, mnr = pair(altruism=0.5)
    base = sim.trust_base.copy()
    sim.step(0)
    assert sim.history["minority_starvation_rate"][-1] == 0.0
    assert sim.trust_in[mnr] == pytest.approx(base[mnr] + sim.p.trust_gain)
    assert sim.trust_in[maj] == pytest.approx(base[maj] + GIVER_TRUST_SHARE * sim.p.trust_gain)


def test_partial_help_moves_trust_by_the_covered_share():
    # The giver can cover a quarter of the 0.1 need (no trust gating, to keep the arithmetic exact)
    sim, maj, mnr = pair(altruism=0.025, trust_half=0.0)
    base = sim.trust_base.copy()
    sim.step(0)
    expected = 0.25 * sim.p.trust_gain - 0.75 * sim.p.trust_loss
    assert sim.trust_in[mnr] == pytest.approx(base[mnr] + expected)


def test_trust_reverts_toward_baseline():
    sim, _, _ = pair(altruism=0.0, base_minority=1.0, trust_reversion=0.02)
    sim.trust_in[:] = 0.0
    sim.trust_out[:] = 1.0
    sim.step(0)
    np.testing.assert_allclose(sim.trust_in, 0.02 * sim.trust_base)
    np.testing.assert_allclose(sim.trust_out, 1.0 - 0.02 * (1.0 - sim.trust_base))


@pytest.mark.parametrize("engagement", [0, 1])
def test_trust_settles_away_from_the_bounds(engagement):
    df = Simulation(Params(N=120, days=150, seed=7, engagement=engagement)).run()
    for col in ["avg_trust", "avg_trust_in", "avg_trust_out"]:
        assert df[col].between(0, 1).all(), col
        assert 0.2 < df[col].tail(50).mean() < 0.9, col
    # Settled: the average barely moves between the middle and the end of the run
    assert abs(df["avg_trust"].iloc[-50:].mean() - df["avg_trust"].iloc[-100:-50].mean()) < 0.03
