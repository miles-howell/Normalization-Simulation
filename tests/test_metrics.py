import math

import numpy as np
import pytest

from normalization_sim.sim import (
    N_AFFILIATIONS,
    OPINION_BINS,
    Params,
    Simulation,
    entropy,
    starvation_rate,
)


# --- entropy -----------------------------------------------------------------

def test_entropy_uniform_over_all_possible_categories_is_one():
    assert entropy(list(range(10)) * 3, 10) == pytest.approx(1.0)


def test_entropy_two_equal_bins_out_of_ten():
    # H = 1 bit, normalized by log2(10)
    assert entropy([0, 0, 9, 9], 10) == pytest.approx(1 / math.log2(10))
    assert entropy([0, 0, 9, 9], 10) == pytest.approx(0.30103, abs=1e-5)


def test_entropy_fewer_present_categories_scores_lower():
    two_bins = entropy([0, 1] * 5, 10)
    ten_bins = entropy(list(range(10)), 10)
    assert two_bins < ten_bins


def test_entropy_skewed_distribution():
    # p = (3/4, 1/4): H = 2 - (3/4) log2 3 ≈ 0.811278 bits; 4 possible categories -> / 2
    labels = ["a", "a", "a", "b"]
    expected = (2 - 0.75 * math.log2(3)) / 2
    assert entropy(labels, 4) == pytest.approx(expected)
    assert entropy(labels, 4) == pytest.approx(0.405639, abs=1e-6)


def test_entropy_single_category_is_positive_zero():
    h = entropy([3, 3, 3, 3], 10)
    assert h == 0.0
    assert math.copysign(1.0, h) == 1.0  # not -0.0
    assert str(h) == "0.0"


def test_entropy_empty_and_degenerate_inputs():
    assert entropy([], 10) == 0.0
    assert entropy(["none", "x"], 1) == 0.0


def test_entropy_rejects_more_labels_than_categories():
    with pytest.raises(ValueError):
        entropy([0, 1, 2], 2)


def test_affiliation_categories_include_none():
    assert N_AFFILIATIONS == 6
    assert OPINION_BINS == 10


# --- starvation --------------------------------------------------------------

def test_starvation_rate_by_group():
    resources = np.array([0.4, 0.6, 0.45, 1.0, 0.9, 0.3])
    is_minority = np.array([True, True, True, False, False, False])
    # minority: 0.4, 0.45 below 0.5 -> 2/3; majority: 0.3 -> 1/3; overall: 3/6
    assert starvation_rate(resources, 0.5, is_minority) == pytest.approx(2 / 3)
    assert starvation_rate(resources, 0.5, ~is_minority) == pytest.approx(1 / 3)
    assert starvation_rate(resources, 0.5) == pytest.approx(0.5)


def test_starvation_rate_at_floor_is_not_starving():
    assert starvation_rate(np.array([0.5, 0.5]), 0.5) == 0.0


def test_starvation_rate_empty_group_is_nan():
    resources = np.array([1.0, 0.2])
    assert math.isnan(starvation_rate(resources, 0.5, np.array([False, False])))


# --- simulation history ------------------------------------------------------

def test_history_starvation_columns_are_consistent():
    p = Params(N=60, days=5, seed=3)
    sim = Simulation(p)
    df = sim.run()
    share = sim.is_minority.mean()
    for col in ["minority_starvation_rate", "majority_starvation_rate", "overall_starvation_rate",
                "diversity", "affil_entropy"]:
        assert len(df[col]) == p.days
        assert df[col].between(0, 1).all(), col
    # The overall rate is the population-weighted mix of the two group rates
    mixed = share * df["minority_starvation_rate"] + (1 - share) * df["majority_starvation_rate"]
    np.testing.assert_allclose(df["overall_starvation_rate"], mixed)


def test_history_minority_rate_with_no_minority_is_nan():
    df = Simulation(Params(N=60, days=2, share_minority=0.0, seed=3)).run()
    assert df["minority_starvation_rate"].isna().all()
    assert df["majority_starvation_rate"].notna().all()
