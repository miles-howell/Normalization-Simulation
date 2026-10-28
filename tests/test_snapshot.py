import numpy as np
import pandas as pd

from normalization_sim.sim import Params, Simulation


def test_iter_days_matches_run():
    a = Simulation(Params(N=40, days=5, seed=3))
    days = list(a.iter_days())
    df_a = pd.DataFrame(a.history)
    df_b = Simulation(Params(N=40, days=5, seed=3)).run()
    assert days == list(range(5))
    pd.testing.assert_frame_equal(df_a, df_b)


def test_snapshot_is_a_copy_of_per_agent_state():
    sim = Simulation(Params(N=30, days=2, seed=1))
    snap = sim.snapshot()
    assert set(snap) == {"opinions", "resources", "on_hand", "affil", "trust_in", "trust_out", "is_minority"}
    assert all(len(v) == 30 for v in snap.values())
    before = snap["opinions"].copy()
    sim.run()
    np.testing.assert_array_equal(snap["opinions"], before)
    assert not np.array_equal(sim.opinions, before)


def test_on_hand_matches_starvation_metric():
    sim = Simulation(Params(N=60, days=4, seed=5))
    for _ in sim.iter_days():
        starving = (sim.snapshot()["on_hand"] < sim.p.survival_floor).mean()
        assert starving == sim.history["overall_starvation_rate"][-1]
