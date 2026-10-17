"""Trivial player.py guard tests: import-safe module, selectors wired to config."""
import inspect

from chessbot import player
from chessbot.config import CONFIG


def test_get_state_js_contains_all_config_selectors():
    for sel in (CONFIG.board_selector, CONFIG.board_fallback,
                CONFIG.move_node_selector, CONFIG.move_node_alt):
        assert sel in player.GET_STATE_JS, f"GET_STATE_JS missing {sel!r}"


def test_play_signature_accepts_dry_run():
    params = inspect.signature(player.play).parameters
    assert "dry_run" in params
