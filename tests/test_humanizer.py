import random

from chessbot.config import CONFIG
from chessbot.humanizer import think_time_ms

def test_bounds():
    for _ in range(500):
        t = think_time_ms(remaining_ms=60_000, median_ms=2600, sigma=0.9,
                          move_min_ms=700, max_clock_fraction=0.06)
        assert 700 <= t <= 3600  # 6% of 60s

def test_short_clock_capped_at_fraction():
    # C1: the clock-fraction cap must win over move_min_ms;
    # 6% of 500ms = 30ms, never the 700ms floor (flag-fall).
    t = think_time_ms(remaining_ms=500, median_ms=CONFIG.think_median_ms,
                      sigma=CONFIG.think_sigma, move_min_ms=CONFIG.move_min_ms,
                      max_clock_fraction=CONFIG.max_clock_fraction)
    assert 0 <= t <= 30

def test_resampling_avoids_cap_point_mass():
    # I4: clamping used to park >=50% of samples exactly on the cap.
    rng = random.Random(7)
    cap = int(30_000 * 0.06)
    draws = [think_time_ms(remaining_ms=30_000, median_ms=2600, sigma=0.9,
                           move_min_ms=700, max_clock_fraction=0.06, rng=rng)
             for _ in range(200)]
    assert all(t <= cap for t in draws)
    assert not all(t == cap for t in draws)
    assert sum(t == cap for t in draws) < 100

def test_seeded_rng_is_deterministic_and_bounded():
    kwargs = dict(remaining_ms=60_000, median_ms=2600, sigma=0.9,
                  move_min_ms=700, max_clock_fraction=0.06)
    t1 = think_time_ms(rng=random.Random(123), **kwargs)
    t2 = think_time_ms(rng=random.Random(123), **kwargs)
    assert t1 == t2
    assert 700 <= t1 <= 3600
