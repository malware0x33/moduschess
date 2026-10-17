import pytest
from chessbot.clock import parse_clock_ms

@pytest.mark.parametrize("text,expected", [
    ("1:32", 92_000), ("0:05", 5_000), ("10:00", 600_000),
    ("1:02:03", 3_723_000), ("0:00", 0), ("", None), ("abc", None), ("2:60", None),
])
def test_parse_clock_ms(text, expected):
    assert parse_clock_ms(text) == expected
