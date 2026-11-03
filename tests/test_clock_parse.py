import asyncio

import chess
import pytest

from chessbot.clock import parse_clock_ms, read_clock_ms

@pytest.mark.parametrize("text,expected", [
    ("1:32", 92_000), ("0:05", 5_000), ("10:00", 600_000),
    ("1:02:03", 3_723_000), ("0:00", 0), ("9.8", 9_800),
    ("0:09.8", 9_800), ("", None), ("abc", None), ("NaN", None),
    ("0:NaN", None), ("Infinity", None), ("-1", None), ("2:60", None),
])
def test_parse_clock_ms(text, expected):
    assert parse_clock_ms(text) == expected


class FakeTab:
    def __init__(self, value):
        self.value = value
        self.expression = None

    async def eval_js(self, expression):
        self.expression = expression
        return self.value


@pytest.mark.parametrize(
    "color,side,value,expected",
    [
        (chess.WHITE, "white", "1:32", 92_000),
        (chess.BLACK, "black", "0:05", 5_000),
    ],
)
def test_read_clock_selects_requested_color(color, side, value, expected):
    tab = FakeTab(value)
    assert asyncio.run(read_clock_ms(tab, color)) == expected
    assert f"clock-{side}" in tab.expression
    assert '[role="timer"]' in tab.expression
