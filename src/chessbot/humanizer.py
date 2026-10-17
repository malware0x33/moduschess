import math
import random

def think_time_ms(remaining_ms: int, median_ms: int, sigma: float,
                  move_min_ms: int, max_clock_fraction: float,
                  rng: random.Random | None = None) -> int:
    """Lognormal think time, hard-capped at max_clock_fraction of the clock.

    Resamples up to 50 times to stay within [min(move_min_ms, cap), cap]
    (avoiding the clamp point-mass); falls back to a uniform draw in that
    range. cap wins over the floor when the clock is short - never flags.
    """
    rng = rng or random.Random()
    cap = int(remaining_ms * max_clock_fraction)
    lo = min(move_min_ms, cap)
    for _ in range(50):
        t = int(rng.lognormvariate(math.log(median_ms), sigma))
        if lo <= t <= cap:
            return t
    return rng.randint(lo, cap)
