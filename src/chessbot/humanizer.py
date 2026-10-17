import random, math

def think_time_ms(remaining_ms: int, median_ms: int, sigma: float,
                  move_min_ms: int, max_clock_fraction: float) -> int:
    cap = max(move_min_ms, int(remaining_ms * max_clock_fraction))
    t = random.lognormvariate(math.log(median_ms), sigma)
    return int(max(move_min_ms, min(t, cap)))
