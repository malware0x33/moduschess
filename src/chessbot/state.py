"""Browser snapshots and mutable session state for the Chessbot player."""

from dataclasses import dataclass
from enum import Enum
import json
import re
from typing import TypedDict

import chess

from chessbot.board_reader import moves_to_board
from chessbot.cdp import SHADOW_QUERY_JS
from chessbot.config import CONFIG

CLICK_ACK_TIMEOUT_S = 5.0


class BrowserState(TypedDict, total=False):
    """Atomic game-page snapshot returned by :data:`GET_STATE_JS`."""

    rect: list[float]
    moves: str
    move_count: int
    cls: str
    flipped: bool
    url: str
    board_present: bool
    game_over: bool
    result_text: str | None


class GamePhase(str, Enum):
    """Lifecycle phase for the currently monitored Chess.com tab."""

    WAITING_FOR_GAME = "waiting_for_game"
    PLAYING = "playing"
    GAME_FINISHED = "game_finished"


@dataclass
class PlayerState:
    """Mutable state retained across iterations of one player session."""

    phase: GamePhase = GamePhase.WAITING_FOR_GAME
    game_url: str | None = None
    last_played: int = -1
    low_score_turns: int = 0
    resolved_color: chess.Color | None = None
    attached: bool = False
    last_status: str | None = None
    pending_ply: int | None = None
    pending_deadline: float | None = None
    pending_move: chess.Move | None = None
    pending_url: str | None = None

    def begin_game(
        self,
        url: str,
        color: chess.Color | None,
    ) -> None:
        """Reset per-game state and enter the playing phase."""
        self.phase = GamePhase.PLAYING
        self.game_url = url
        self.last_played = -1
        self.low_score_turns = 0
        self.resolved_color = color
        self.attached = False
        self.last_status = None
        self.clear_pending()

    def finish_game(self) -> None:
        """Enter the finished phase and discard pending move state."""
        self.phase = GamePhase.GAME_FINISHED
        self.last_status = None
        self.clear_pending()

    def wait_for_game(self) -> None:
        """Reset the session to wait for a future game."""
        self.phase = GamePhase.WAITING_FOR_GAME
        self.game_url = None
        self.last_played = -1
        self.low_score_turns = 0
        self.resolved_color = None
        self.attached = False
        self.last_status = None
        self.clear_pending()

    def set_pending(
        self,
        *,
        ply: int,
        deadline: float,
        move: chess.Move,
        url: str,
    ) -> None:
        """Record a submitted move while waiting for DOM acknowledgement."""
        self.pending_ply = ply
        self.pending_deadline = deadline
        self.pending_move = move
        self.pending_url = url

    def clear_pending(self) -> None:
        """Clear all move-acknowledgement state as one operation."""
        self.pending_ply = None
        self.pending_deadline = None
        self.pending_move = None
        self.pending_url = None


GET_STATE_JS = """
(() => {
%s
  const roots = collectRoots();
  const board = queryFirstFromRoots('%s', roots) || queryFirstFromRoots('%s', roots);
  const isVisible = element => {
    const r = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return r.width > 0 && r.height > 0 &&
      style.display !== 'none' && style.visibility !== 'hidden';
  };
  const gameOverNode = queryAllFromRoots(%s, roots).find(isVisible) || null;
  const gameOverRoots = gameOverNode ? collectRoots(gameOverNode) : [];
  const resultNode = gameOverNode
    ? queryFirstFromRoots(%s, gameOverRoots)
    : null;
  const resultText = ((resultNode || gameOverNode)?.textContent || '')
    .replace(/\\s+/g, ' ').trim();
  const pageState = {
    url: location.href,
    board_present: Boolean(board),
    game_over: Boolean(gameOverNode),
    result_text: resultText || null,
  };
  if (!board) return pageState;
  const r = board.getBoundingClientRect();
  const nodes = queryAllFromRoots('%s', roots);
  const container = nodes.length ? nodes : queryAllFromRoots('%s', roots);
  const moveTokens = [...container].map(node => {
    const clone = node.cloneNode(true);
    clone.querySelectorAll('[data-figurine]').forEach(icon => {
      icon.replaceWith(icon.getAttribute('data-figurine') || '');
    });
    return (clone.textContent || '').replace(/\\s+/g, '');
  }).filter(Boolean);
  return {
    ...pageState,
    rect: [r.x, r.y, r.width, r.height],
    moves: moveTokens.join(' '),
    move_count: moveTokens.length,
    cls: String(board.className),
    flipped: board.classList.contains('flipped'),
  };
})()
""" % (
    SHADOW_QUERY_JS,
    CONFIG.board_selector,
    CONFIG.board_fallback,
    json.dumps(CONFIG.game_over_selector),
    json.dumps(CONFIG.game_result_selector),
    CONFIG.move_node_selector,
    CONFIG.move_node_alt,
)


def promotion_js(selector: str) -> str:
    """Return shadow-DOM-aware JavaScript for a promotion choice centre."""
    return """(() => {
%s
  const el = queryDeep(%s);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return [r.x + r.width / 2, r.y + r.height / 2];
})()""" % (SHADOW_QUERY_JS, json.dumps(selector))


def board_white_bottom(state: BrowserState) -> bool:
    """Return the board orientation reported by a browser snapshot."""
    if "flipped" in state:
        return not bool(state["flipped"])
    return "flipped" not in str(state.get("cls", "")).split()


def resolve_color(
    color: chess.Color | None,
    state: BrowserState,
) -> chess.Color:
    """Use an explicit color or infer it once from board orientation."""
    if color is not None:
        return color
    return chess.WHITE if board_white_bottom(state) else chess.BLACK


def side_name(color: chess.Color) -> str:
    """Return the display name for a python-chess color value."""
    return "white" if color == chess.WHITE else "black"


def is_game_url(url: str) -> bool:
    """Return whether *url* identifies a supported live game."""
    return re.search(CONFIG.game_url_regex, url) is not None


def describe_game_result(
    state: BrowserState,
    board: chess.Board | None = None,
) -> str:
    """Return a concise site result, with a board outcome as fallback."""
    text = " ".join(str(state.get("result_text") or "").split())
    if text:
        return text[:300]
    if board is not None:
        outcome = board.outcome()
        if outcome is not None:
            termination = outcome.termination.name.lower().replace("_", " ")
            return f"{outcome.result()} {termination}"
    return "result unavailable"


def board_from_state(state: BrowserState) -> chess.Board:
    """Build and validate a board from one atomic browser snapshot."""
    board = moves_to_board(state["moves"])
    move_count = state.get("move_count")
    if move_count is not None and len(board.move_stack) != move_count:
        raise ValueError(
            f"parsed {len(board.move_stack)} of {move_count} move nodes"
        )
    return board
