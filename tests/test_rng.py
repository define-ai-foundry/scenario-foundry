"""Tests for scenario_foundry.rng."""

import random

import numpy as np

from scenario_foundry.rng import seed_all


def test_seed_all_makes_stdlib_random_reproducible():
    seed_all(42)
    first = [random.random() for _ in range(5)]
    seed_all(42)
    second = [random.random() for _ in range(5)]
    assert first == second


def test_seed_all_makes_numpy_reproducible():
    seed_all(42)
    first = np.random.rand(5)
    seed_all(42)
    second = np.random.rand(5)
    assert np.array_equal(first, second)


def test_seed_all_distinct_seeds_diverge():
    seed_all(1)
    a = [random.random() for _ in range(5)]
    seed_all(2)
    b = [random.random() for _ in range(5)]
    assert a != b
