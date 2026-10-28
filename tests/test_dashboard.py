from dataclasses import fields

import numpy as np
import pytest

from normalization_sim.dashboard import (
    CONTROLS, PRESETS, Params, affiliation_shares, opinion_density, params_key, parse_days, preset_params,
    run_recorded, summarize,
)


def test_controls_cover_params_and_defaults_fit_their_ranges():
    assert set(CONTROLS) == {f.name for f in fields(Params)}
    for name in PRESETS:
        p = preset_params(name)
        for c in CONTROLS.values():
            if c.kind in ("slider", "int"):
                assert c.lo <= getattr(p, c.field) <= c.hi, (name, c.field)


def test_parse_days():
    assert parse_days("100, 60  60") == (60, 100)
    assert parse_days("") == ()
    with pytest.raises(ValueError):
        parse_days("sixty")


def test_params_key_is_hashable_and_tracks_changes():
    a, b = Params(), Params(lambda_=0.3)
    assert hash(params_key(a)) is not None
    assert params_key(a) == params_key(Params())
    assert params_key(a) != params_key(b)


def test_run_recorded_matches_plain_run_and_shapes():
    p = Params(N=30, days=6, seed=2)
    r = run_recorded(p)
    assert r.opinions.shape == r.resources.shape == r.affil.shape == (6, 30)
    assert list(r.metrics["day"]) == list(range(6))
    np.testing.assert_allclose(r.opinions[-1].std(), r.metrics["opinion_std"].iloc[-1])


def test_opinion_density_columns_sum_to_one():
    ops = np.random.default_rng(0).uniform(-1, 1, (5, 50))
    ops[0, 0] = 1.0  # the top edge is included in the last bin
    centers, dens = opinion_density(ops, bins=8)
    assert len(centers) == 8 and dens.shape == (8, 5)
    np.testing.assert_allclose(dens.sum(axis=0), 1.0)


def test_affiliation_shares_sum_to_one():
    r = run_recorded(Params(N=30, days=3, seed=4))
    np.testing.assert_allclose(affiliation_shares(r.affil).sum(axis=1), 1.0)


def test_summarize_uses_last_days():
    r = run_recorded(Params(N=20, days=8, seed=1))
    assert summarize(r.metrics, last=3)["stability"] == pytest.approx(r.metrics["stability"].tail(3).mean())
