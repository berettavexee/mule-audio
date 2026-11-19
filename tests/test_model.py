"""The adaptive models (core/model.c) through mule_stream_cost: close to the entropy, contexts
kept apart, resets relearned."""
import numpy as np

from mule import native


def entropy_bits(p, n):
    """n symbols' entropy (bits) under the distribution p."""
    p = np.asarray(p, float)
    return -n * np.sum(p * np.log2(p))


def test_adaptive_cost_close_to_entropy():
    """On a stationary source the adaptive model costs less than 2 % over the entropy"""
    rng = np.random.default_rng(0)
    p = np.array([0.6, 0.2, 0.1, 0.05, 0.03, 0.02])
    n = 200000
    sym = rng.choice(len(p), n, p=p)
    bits = native.stream_cost(16, 1, np.zeros(n, int), sym)
    h = entropy_bits(p, n)
    assert h < bits < h * 1.02          # adaptation + 16-symbol alphabet + min frequency: < 2 %


def test_contexts_are_separate_and_reset_costs():
    """Each context learns its own symbol; resetting the models makes them relearn"""
    rng = np.random.default_rng(1)
    n = 50000
    ctx = rng.integers(0, 2, n)
    sym = np.where(ctx == 0, 0, 5)      # deterministic per context: nearly free
    bits = native.stream_cost(16, 2, ctx, sym)
    assert bits < 0.02 * n
    with_resets = native.stream_cost(16, 2, ctx, sym, resets=range(1000, n, 1000))
    assert with_resets > bits * 2       # relearning after each reset costs
