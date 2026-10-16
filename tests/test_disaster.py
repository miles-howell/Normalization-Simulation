import math

import numpy as np
import pytest

from normalization_sim.sim import Params, Simulation


def society(opinions=(0.3, -0.3), **kw):
    """Two unconnected majority agents with no shocks, so on-hand resources on day 0 are exactly 1.0."""
    params = dict(N=2, share_minority=0.0, p_edge=0.0, shock_sd=0.0, opinion_noise=0.0,
                  trust_reversion=0.0, seed=3)
    params.update(kw)
    sim = Simulation(Params(**params))
    sim.affil[:] = "none"
    sim.opinions[:] = opinions
    return sim


def savings_after(on_hand, p):
    return (on_hand - p.survival_floor) * (1 - p.resource_decay)


def test_no_disaster_by_default():
    df = Simulation(Params(N=60, days=5, seed=3)).run()
    assert (df["disaster_loss"] == 0).all()
    assert df["disaster_cooperation"].isna().all()


def test_working_response_limits_damage_and_builds_out_group_trust():
    sim = society(disaster_days=(0,))
    sim.trust_out[:] = 0.8
    sim.step(0)
    loss = sim.p.disaster_severity * (1 - sim.p.disaster_mitigation)
    assert sim.history["disaster_loss"] == [pytest.approx(loss)]
    assert sim.history["disaster_cooperation"] == [pytest.approx(0.8)]
    np.testing.assert_allclose(sim.resources, savings_after(1 - loss, sim.p))
    np.testing.assert_allclose(sim.trust_out, 0.8 + sim.p.disaster_trust_shift)


def test_failed_response_takes_full_damage_and_erodes_out_group_trust():
    sim = society(disaster_days=(0,))
    sim.trust_out[:] = 0.3
    sim.step(0)
    assert sim.history["disaster_loss"] == [pytest.approx(sim.p.disaster_severity)]
    np.testing.assert_allclose(sim.resources, savings_after(1 - sim.p.disaster_severity, sim.p))
    np.testing.assert_allclose(sim.trust_out, 0.3 - sim.p.disaster_trust_shift)


def test_response_is_only_as_strong_as_the_less_willing_camp():
    sim = society(disaster_days=(0,))
    sim.trust_out[:] = [0.9, 0.2]
    sim.step(0)
    assert sim.history["disaster_cooperation"] == [pytest.approx(0.2)]
    assert sim.history["disaster_loss"] == [pytest.approx(sim.p.disaster_severity)]


def test_one_camp_uses_in_group_trust():
    sim = society(opinions=(0.3, 0.6))
    sim.trust_in[:] = 0.7
    sim.trust_out[:] = 0.0
    assert sim.disaster_cooperation() == pytest.approx(0.7)


def test_trigger_disaster_strikes_once_on_the_next_step():
    sim = society()
    sim.step(0)
    sim.trigger_disaster()
    sim.step(1)
    sim.step(2)
    losses = sim.history["disaster_loss"]
    assert losses[0] == 0 and losses[1] > 0 and losses[2] == 0
    assert math.isnan(sim.history["disaster_cooperation"][2])
