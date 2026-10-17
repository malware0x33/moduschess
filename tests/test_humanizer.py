from chessbot.humanizer import think_time_ms

def test_bounds():
    for _ in range(500):
        t = think_time_ms(remaining_ms=60_000, median_ms=2600, sigma=0.9,
                          move_min_ms=700, max_clock_fraction=0.06)
        assert 700 <= t <= 3600  # 6% of 60s
