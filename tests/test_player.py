"""Trivial player.py guard tests: import-safe module, selectors wired to config."""
import asyncio
import inspect
import random
import sys
from collections import Counter
from types import SimpleNamespace

import chess
import pytest

from chessbot import player
from chessbot.config import CONFIG


def test_version_flag_exits_before_engine_start(monkeypatch, capsys):
    def engine_must_not_start(*_args, **_kwargs):
        raise AssertionError("version output must not start Stockfish")

    monkeypatch.setattr(sys, "argv", ["main.py", "-v"])
    monkeypatch.setattr(player, "StockfishPolicy", engine_must_not_start)

    with pytest.raises(SystemExit) as exit_info:
        player.main()

    assert exit_info.value.code == 0
    assert capsys.readouterr().out == (
        "Version 1.0.0\n"
        "Written by J A G\n"
        "Join discord https://discord.gg/h658Sa3sx\n"
    )


def test_get_state_js_contains_all_config_selectors():
    for sel in (CONFIG.board_selector, CONFIG.board_fallback,
                CONFIG.move_node_selector, CONFIG.move_node_alt):
        assert sel in player.GET_STATE_JS, f"GET_STATE_JS missing {sel!r}"


def test_get_state_js_rebuilds_piece_letters_and_counts_nodes():
    assert CONFIG.move_node_selector == ".node.main-line-ply"
    assert "queryAllDeep" in player.GET_STATE_JS
    assert "[data-figurine]" in player.GET_STATE_JS
    assert "replaceWith" in player.GET_STATE_JS
    assert "move_count" in player.GET_STATE_JS


def test_promotion_lookup_traverses_shadow_roots():
    script = player.promotion_js("[data-piece='q']")
    assert "queryDeep" in script
    assert "[data-piece='q']" in script


def test_play_signature_accepts_dry_run():
    params = inspect.signature(player.play).parameters
    assert "dry_run" in params


@pytest.mark.parametrize(
    "state,expected",
    [
        ({"flipped": False}, chess.WHITE),
        ({"flipped": True}, chess.BLACK),
        ({"cls": "board"}, chess.WHITE),
        ({"cls": "board flipped"}, chess.BLACK),
    ],
)
def test_auto_color_follows_board_orientation(state, expected):
    assert player.resolve_color(None, state) == expected


def test_explicit_color_overrides_board_orientation():
    assert player.resolve_color(chess.WHITE, {"flipped": True}) == chess.WHITE
    assert player.resolve_color(chess.BLACK, {"flipped": False}) == chess.BLACK


def test_board_from_state_rejects_partial_move_parse():
    with pytest.raises(ValueError, match="parsed 1 of 2 move nodes"):
        player.board_from_state({"moves": "e4 garbage", "move_count": 2})


def test_play_reports_wait_state_without_poll_spam(monkeypatch, capsys):
    waiting = {
        "rect": [0, 0, 800, 800],
        "moves": "e4",
        "move_count": 1,
        "cls": "board",
        "flipped": False,
        "url": "https://www.chess.com/game/123",
    }
    game_over = {
        **waiting,
        "moves": "f3 e5 g4 Qh4#",
        "move_count": 4,
    }

    class ScenarioComplete(Exception):
        pass

    class FakeTab:
        def __init__(self):
            self.states = iter((waiting, waiting, game_over))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return None

        async def eval_js(self, _expression):
            try:
                return next(self.states)
            except StopIteration:
                raise ScenarioComplete from None

    class NoAnalysePolicy:
        def analyse(self, _board):
            raise AssertionError("engine must not run while it is not the bot's turn")

    async def no_sleep(_seconds):
        return None

    fake_tab = FakeTab()
    monkeypatch.setattr(player, "find_tab", lambda *_args: "ws://fake")
    monkeypatch.setattr(player, "Tab", lambda _url: fake_tab)
    monkeypatch.setattr(player.asyncio, "sleep", no_sleep)

    with pytest.raises(ScenarioComplete):
        asyncio.run(
            player.play(NoAnalysePolicy(), color=chess.WHITE, dry_run=True)
        )

    output = capsys.readouterr().out
    assert output.count("[wait] black to move at ply 1; bot is white") == 1
    assert "[game over]" in output


def test_zero_clock_reaches_timing_without_fallback(monkeypatch):
    initial = {
        "rect": [0, 0, 800, 800],
        "moves": "",
        "move_count": 0,
        "cls": "board",
        "flipped": False,
        "url": "https://www.chess.com/game/123",
    }
    game_over = {
        **initial,
        "moves": "f3 e5 g4 Qh4#",
        "move_count": 4,
    }

    class ScenarioComplete(Exception):
        pass

    class FakeTab:
        def __init__(self):
            self.states = iter((initial, initial, game_over))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return None

        async def eval_js(self, _expression):
            try:
                return next(self.states)
            except StopIteration:
                raise ScenarioComplete from None

    class Policy:
        def analyse(self, _board):
            return [(chess.Move.from_uci("e2e4"), 20)]

    async def zero_clock(_tab, _color):
        return 0

    async def no_sleep(_seconds):
        return None

    observed = []

    def zero_think_time(remaining_ms, *_args):
        observed.append(remaining_ms)
        return 0

    monkeypatch.setattr(player, "find_tab", lambda *_args: "ws://fake")
    monkeypatch.setattr(player, "Tab", lambda _url: FakeTab())
    monkeypatch.setattr(player, "read_clock_ms", zero_clock)
    monkeypatch.setattr(player, "think_time_ms", zero_think_time)
    monkeypatch.setattr(player.asyncio, "sleep", no_sleep)

    with pytest.raises(ScenarioComplete):
        asyncio.run(player.play(Policy(), color=chess.WHITE, dry_run=True))
    assert observed == [0]


@pytest.mark.parametrize("after_click", ("unchanged", "missing", "unparseable"))
def test_unacknowledged_click_stops_instead_of_waiting_forever(
    monkeypatch, after_click
):
    initial = {
        "rect": [0, 0, 800, 800],
        "moves": "",
        "move_count": 0,
        "cls": "board",
        "flipped": False,
        "url": "https://www.chess.com/game/123",
    }

    class FakeTab:
        def __init__(self):
            self.clicks = []
            self.state_reads = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return None

        async def eval_js(self, expression):
            if CONFIG.promotion_selector in expression:
                return None
            self.state_reads += 1
            if self.state_reads <= 2 or after_click == "unchanged":
                return initial
            if after_click == "missing":
                return None
            return {**initial, "moves": "not-a-move", "move_count": 1}

        async def click(self, x, y):
            self.clicks.append((x, y))

    class Policy:
        def analyse(self, _board):
            return [(chess.Move.from_uci("e2e4"), 20)]

    async def clock(_tab, _color):
        return 60_000

    async def no_sleep(_seconds):
        return None

    monotonic_values = iter((100.0, 104.0, 106.0))
    fake_tab = FakeTab()
    monkeypatch.setattr(player, "find_tab", lambda *_args: "ws://fake")
    monkeypatch.setattr(player, "Tab", lambda _url: fake_tab)
    monkeypatch.setattr(player, "read_clock_ms", clock)
    monkeypatch.setattr(player, "think_time_ms", lambda *_args: 0)
    monkeypatch.setattr(player.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(
        player,
        "time",
        SimpleNamespace(monotonic=lambda: next(monotonic_values)),
    )

    with pytest.raises(RuntimeError, match="move click was not acknowledged"):
        asyncio.run(player.play(Policy(), color=chess.WHITE))
    assert len(fake_tab.clicks) == 2


def test_acknowledgement_rejects_a_different_move(monkeypatch):
    initial = {
        "rect": [0, 0, 800, 800],
        "moves": "",
        "move_count": 0,
        "cls": "board",
        "flipped": False,
        "url": "https://www.chess.com/game/123",
    }
    different_move = {**initial, "moves": "d4", "move_count": 1}

    class FakeTab:
        def __init__(self):
            self.clicks = []
            self.state_reads = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return None

        async def eval_js(self, expression):
            if CONFIG.promotion_selector in expression:
                return None
            self.state_reads += 1
            return initial if self.state_reads <= 2 else different_move

        async def click(self, x, y):
            self.clicks.append((x, y))

    class Policy:
        def analyse(self, _board):
            return [(chess.Move.from_uci("e2e4"), 20)]

    async def clock(_tab, _color):
        return 60_000

    async def no_sleep(_seconds):
        return None

    monotonic_values = iter((100.0, 101.0))
    fake_tab = FakeTab()
    monkeypatch.setattr(player, "find_tab", lambda *_args: "ws://fake")
    monkeypatch.setattr(player, "Tab", lambda _url: fake_tab)
    monkeypatch.setattr(player, "read_clock_ms", clock)
    monkeypatch.setattr(player, "think_time_ms", lambda *_args: 0)
    monkeypatch.setattr(player.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(
        player,
        "time",
        SimpleNamespace(monotonic=lambda: next(monotonic_values)),
    )

    with pytest.raises(RuntimeError, match="advanced with d2d4, expected e2e4"):
        asyncio.run(player.play(Policy(), color=chess.WHITE))
    assert len(fake_tab.clicks) == 2


def test_sample_move_stays_within_ranked_and_favors_best():
    ranked = [
        (chess.Move.from_uci("e2e4"), 40),
        (chess.Move.from_uci("d2d4"), 10),
        (chess.Move.from_uci("g1f3"), -20),
    ]
    random.seed(7)
    picks = Counter(
        player.sample_move(ranked, CONFIG.sample_temperature_cp) for _ in range(500)
    )
    assert set(picks) <= {move for move, _ in ranked}
    assert picks[chess.Move.from_uci("e2e4")] == max(picks.values())


def test_sample_move_mate_gap_never_overflows():
    ranked = [
        (chess.Move.from_uci("e1e8"), 9999),
        (chess.Move.from_uci("g1f1"), 683),
    ]
    random.seed(3)
    for _ in range(100):
        assert player.sample_move(
            ranked, CONFIG.sample_temperature_cp
        ) in {move for move, _ in ranked}


def test_sample_move_single_entry_is_forced():
    move = chess.Move.from_uci("a2a3")
    assert player.sample_move([(move, 0)], CONFIG.sample_temperature_cp) == move


def test_play_waits_on_home_reports_results_and_accepts_a_next_game(
    monkeypatch, capsys
):
    home = {
        "url": "https://www.chess.com/home",
        "board_present": False,
        "game_over": False,
        "result_text": None,
    }
    first_finished = {
        "url": "https://www.chess.com/game/live/123",
        "board_present": True,
        "game_over": True,
        "result_text": "0-1 Black won by resignation",
        "rect": [0, 0, 800, 800],
        "moves": "e4 e5",
        "move_count": 2,
        "cls": "board",
        "flipped": False,
    }
    second_finished = {
        **first_finished,
        "url": "https://www.chess.com/game/live/456",
        "result_text": "1-0 White won on time",
    }

    class ScenarioComplete(Exception):
        pass

    class FakeTab:
        def __init__(self):
            self.states = iter(
                (home, first_finished, first_finished, home, second_finished)
            )

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return None

        async def eval_js(self, _expression):
            try:
                return next(self.states)
            except StopIteration:
                raise ScenarioComplete from None

    class NoAnalysePolicy:
        def analyse(self, _board):
            raise AssertionError("engine must not run outside an active game")

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(player, "find_tab", lambda *_args: "ws://fake")
    monkeypatch.setattr(player, "Tab", lambda _url: FakeTab())
    monkeypatch.setattr(player.asyncio, "sleep", no_sleep)

    with pytest.raises(ScenarioComplete):
        asyncio.run(
            player.play(NoAnalysePolicy(), color=chess.WHITE, dry_run=True)
        )

    output = capsys.readouterr().out
    assert "[wait] no active game" in output
    assert output.count("[game over]") == 2
    assert "0-1 Black won by resignation" in output
    assert "1-0 White won on time" in output
