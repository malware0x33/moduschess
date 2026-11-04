"""Watch a chess.com game tab, pick Stockfish moves, play them with humanized timing."""
import argparse
import asyncio
import math
import random
import time

import chess

from chessbot.cdp import (
    BrowserConnection,
    CDPError,
    SESSION_NOT_FOUND_CODE,
    Tab,
    find_tab,
)
from chessbot.config import CONFIG
from chessbot.clock import read_clock_ms
from chessbot.engine import StockfishPolicy
from chessbot.humanizer import think_time_ms
from chessbot.mover import square_to_xy
from chessbot.state import (
    BrowserState,
    CLICK_ACK_TIMEOUT_S,
    GET_STATE_JS,
    GamePhase,
    PlayerState,
    board_from_state,
    board_white_bottom,
    describe_game_result,
    is_game_url,
    promotion_js,
    resolve_color,
    side_name,
)

VERSION_TEXT = (
    "Version 1.0.0\n"
    "Written by J A G\n"
    "Join discord https://discord.gg/h658Sa3sx"
)


def sample_move(ranked: list[tuple[chess.Move, int]], temperature_cp: int) -> chess.Move:
    """Softmax sample one move on score gap below best (ranked is best-first).

    Chess.com's server side statistical analysis is the real detector, so always
    playing the engine's best move would stand out; this occasionally plays
    a "near best" alternative. Deltas are negative exponents, so large gaps
    (e.g. mate 9999 vs 683 cp) underflow to weight 0 instead of overflowing.
    """
    best_score = ranked[0][1]
    weights = [
        math.exp(-(best_score - score) / max(temperature_cp, 1))
        for _, score in ranked
    ]
    return random.choices([move for move, _ in ranked], weights=weights, k=1)[0]


def _validated_click_board(
    snapshot: BrowserState | None,
    expected: BrowserState,
    color: chess.Color,
    move: chess.Move,
) -> chess.Board | None:
    """Return a current, safe-to-click board or ``None`` if it changed."""
    if not snapshot:
        return None
    if not bool(snapshot.get("board_present", "rect" in snapshot)):
        return None
    if snapshot.get("game_over"):
        return None
    if (
        snapshot.get("url") != expected.get("url")
        or snapshot.get("moves") != expected.get("moves")
        or snapshot.get("move_count") != expected.get("move_count")
    ):
        return None

    rect = snapshot.get("rect")
    if not isinstance(rect, (list, tuple)) or len(rect) != 4:
        return None
    try:
        x, y, width, height = (float(value) for value in rect)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (x, y, width, height)):
        return None
    if width <= 0 or height <= 0:
        return None

    try:
        board = board_from_state(snapshot)
    except (KeyError, TypeError, ValueError):
        return None
    if board.is_game_over() or board.turn != color or move not in board.legal_moves:
        return None
    return board


async def _recover_click_board(
    tab: Tab,
    expected: BrowserState,
    color: chess.Color,
    move: chess.Move,
) -> tuple[BrowserState, chess.Board]:
    """Recover the CDP session and prove a failed click is safe to replay."""
    snapshot = await tab.eval_js(GET_STATE_JS)
    board = _validated_click_board(snapshot, expected, color, move)
    if board is None:
        raise RuntimeError(
            "board changed after stale CDP mouse input; input was not replayed"
        )
    return snapshot, board


def _promotion_point(value, context: str) -> tuple[float, float]:
    """Return finite promotion coordinates or raise an actionable error."""
    if not value:
        raise RuntimeError(f"promotion choice disappeared {context}")
    try:
        point = tuple(float(item) for item in value)
    except (TypeError, ValueError):
        raise RuntimeError(
            f"promotion choice coordinates were invalid {context}"
        ) from None
    if len(point) != 2 or not all(math.isfinite(item) for item in point):
        raise RuntimeError(f"promotion choice coordinates were invalid {context}")
    return point


async def _click_square_with_recovery(
    tab: Tab,
    square: str,
    state: BrowserState,
    board: chess.Board,
    color: chess.Color,
    move: chess.Move,
) -> tuple[BrowserState, chess.Board]:
    """Click one board square, replaying once after guarded CDP recovery."""
    point = square_to_xy(
        square,
        tuple(state["rect"]),
        board_white_bottom(state),
    )
    try:
        await tab.click(*point)
        return state, board
    except CDPError as error:
        if (
            error.code != SESSION_NOT_FOUND_CODE
            or not tab.supports_session_recovery
        ):
            raise

    recovered_state, recovered_board = await _recover_click_board(
        tab,
        state,
        color,
        move,
    )
    recovered_point = square_to_xy(
        square,
        tuple(recovered_state["rect"]),
        board_white_bottom(recovered_state),
    )
    await tab.click(*recovered_point)
    return recovered_state, recovered_board


async def _click_promotion_with_recovery(
    tab: Tab,
    point: tuple[float, float],
    state: BrowserState,
    board: chess.Board,
    color: chess.Color,
    move: chess.Move,
) -> tuple[BrowserState, chess.Board]:
    """Click a promotion choice, refreshing it before one guarded replay."""
    try:
        await tab.click(*point)
        return state, board
    except CDPError as error:
        if (
            error.code != SESSION_NOT_FOUND_CODE
            or not tab.supports_session_recovery
        ):
            raise

    recovered_state, recovered_board = await _recover_click_board(
        tab,
        state,
        color,
        move,
    )
    recovered_promo = await tab.eval_js(promotion_js(CONFIG.promotion_selector))
    recovered_point = _promotion_point(recovered_promo, "after CDP recovery")
    await tab.click(*recovered_point)
    return recovered_state, recovered_board


async def play(policy, color: chess.Color | None = None, dry_run=False, poll_s=0.4):
    ws = find_tab(CONFIG.cdp_url, CONFIG.watch_url_regex)
    if not ws:
        raise RuntimeError(
            "no matching Chess.com tab - open Home, Play, or a live game"
        )
    if isinstance(ws, BrowserConnection):
        print(
            "[connect] requesting access to the current Chrome profile; "
            "approve Chrome's remote-debugging prompt",
            flush=True,
        )
    async with Tab(ws) as tab:
        session = PlayerState()

        def report_status(message: str) -> None:
            if message != session.last_status:
                print(message, flush=True)
                session.last_status = message

        while True:
            if (
                session.pending_deadline is not None
                and time.monotonic() >= session.pending_deadline
            ):
                raise RuntimeError(
                    f"move click was not acknowledged within "
                    f"{CLICK_ACK_TIMEOUT_S:g}s at ply {session.pending_ply}"
                )
            state = await tab.eval_js(GET_STATE_JS)
            if not state:
                report_status("[wait] Chess.com page is loading")
                await asyncio.sleep(2)
                continue

            url = str(state.get("url", ""))
            board_present = bool(state.get("board_present", "rect" in state))
            if not is_game_url(url) or not board_present:
                if session.phase is not GamePhase.WAITING_FOR_GAME:
                    session.wait_for_game()
                report_status(
                    "[wait] no active game; start one from Chess.com Home "
                    "or Play"
                )
                await asyncio.sleep(poll_s)
                continue

            if (
                session.phase is GamePhase.GAME_FINISHED
                and session.game_url == url
            ):
                report_status("[wait] game finished; waiting for the next game")
                await asyncio.sleep(poll_s)
                continue

            if session.phase is not GamePhase.PLAYING or session.game_url != url:
                session.begin_game(url, color)

            try:
                board = board_from_state(state)
            except ValueError as e:
                if state.get("game_over"):
                    result = describe_game_result(state)
                    print(f"[game over] {result} ({url})", flush=True)
                    session.finish_game()
                else:
                    report_status(f"[board] {e} - retrying next poll")
                await asyncio.sleep(poll_s)
                continue

            if state.get("game_over") or board.is_game_over():
                result = describe_game_result(state, board)
                print(f"[game over] {result} ({url})", flush=True)
                session.finish_game()
                await asyncio.sleep(poll_s)
                continue

            if session.resolved_color is None:
                # resolve only once the game has actually begun (a move exists or
                # a clock is readable) so a lobby/review board can't mislead the
                # orientation-based inference
                if state.get("move_count") == 0 and await read_clock_ms(tab, chess.WHITE) is None:
                    report_status("[wait] game not started yet; waiting to detect your side")
                    await asyncio.sleep(poll_s)
                    continue
                session.resolved_color = resolve_color(None, state)
            if not session.attached:
                orientation = "white" if board_white_bottom(state) else "black"
                mode = "dry-run" if dry_run else "click mode"
                print(
                    f"[attached] playing {side_name(session.resolved_color)} "
                    f"({orientation} at bottom, {mode})",
                    flush=True,
                )
                session.attached = True

            ply = len(board.move_stack)
            if session.pending_ply is not None:
                if state.get("url") != session.pending_url:
                    raise RuntimeError(
                        "game tab changed while waiting for move acknowledgement"
                    )
                if ply > session.pending_ply:
                    observed_move = board.move_stack[session.pending_ply]
                    if observed_move != session.pending_move:
                        raise RuntimeError(
                            f"position advanced with {observed_move}, "
                            f"expected {session.pending_move}"
                        )
                    print(f"[move] acknowledged at ply {ply}", flush=True)
                    session.last_played = session.pending_ply
                    session.clear_pending()
                else:
                    report_status(
                        f"[wait] submitted move at ply {session.pending_ply}; "
                        "waiting for board acknowledgement"
                    )
                    await asyncio.sleep(poll_s)
                    continue

            if board.turn != session.resolved_color:
                report_status(
                    f"[wait] {side_name(board.turn)} to move at ply {ply}; "
                    f"bot is {side_name(session.resolved_color)}"
                )
                await asyncio.sleep(poll_s)
                continue
            if ply <= session.last_played:
                report_status(
                    f"[wait] move for ply {ply + 1} already handled; "
                    "waiting for the board to update"
                )
                await asyncio.sleep(poll_s)
                continue

            remaining_ms = await read_clock_ms(tab, session.resolved_color)
            if remaining_ms is None:
                report_status("[clock] player clock unavailable; using 180 seconds")
                remaining_ms = 180_000
            ranked = policy.analyse(board)
            if not ranked:
                report_status("[wait] engine returned no legal move")
                await asyncio.sleep(poll_s)
                continue
            best_move = sample_move(ranked, CONFIG.sample_temperature_cp)
            best_score = ranked[0][1]
            # resign rail: 3 consecutive turns below threshold
            session.low_score_turns = (
                session.low_score_turns + 1
                if best_score < CONFIG.resign_below_cp
                else 0
            )
            if session.low_score_turns >= 3:
                print(f"[stop] resign threshold at ply {ply} (score {best_score})", flush=True)
                return
            think_ms = think_time_ms(remaining_ms, CONFIG.think_median_ms, CONFIG.think_sigma,
                                     CONFIG.move_min_ms, CONFIG.max_clock_fraction)
            print(
                f"[think] ply {ply + 1}: {best_move} "
                f"(score {best_score}, clock {remaining_ms}ms) for {think_ms}ms",
                flush=True,
            )
            await asyncio.sleep(think_ms / 1000)

            fresh_state = await tab.eval_js(GET_STATE_JS)
            fresh_board = _validated_click_board(
                fresh_state,
                state,
                session.resolved_color,
                best_move,
            )
            if fresh_board is None:
                report_status("[replan] position changed while thinking")
                continue
            state = fresh_state
            board = fresh_board
            ply = len(board.move_stack)

            if dry_run:
                session.last_played = ply
                print(f"[dry-run] would play {best_move}; no click sent", flush=True)
                continue
            state, board = await _click_square_with_recovery(
                tab,
                chess.square_name(best_move.from_square),
                state,
                board,
                session.resolved_color,
                best_move,
            )
            ply = len(board.move_stack)
            await asyncio.sleep(random.uniform(0.10, 0.25))  # humanized pick→drop gap

            destination_state = await tab.eval_js(GET_STATE_JS)
            destination_board = _validated_click_board(
                destination_state,
                state,
                session.resolved_color,
                best_move,
            )
            if destination_board is None:
                report_status("[replan] position changed before destination click")
                continue
            state = destination_state
            board = destination_board
            ply = len(board.move_stack)
            state, board = await _click_square_with_recovery(
                tab,
                chess.square_name(best_move.to_square),
                state,
                board,
                session.resolved_color,
                best_move,
            )
            ply = len(board.move_stack)
            await asyncio.sleep(0.5)
            promo = await tab.eval_js(promotion_js(CONFIG.promotion_selector))
            if promo:
                promotion_state = await tab.eval_js(GET_STATE_JS)
                promotion_board = _validated_click_board(
                    promotion_state,
                    state,
                    session.resolved_color,
                    best_move,
                )
                if promotion_board is None:
                    raise RuntimeError(
                        "position changed before promotion choice; stopping "
                        "to avoid repeating a partially submitted move"
                    )
                refreshed_promo = await tab.eval_js(
                    promotion_js(CONFIG.promotion_selector)
                )
                promotion_point = _promotion_point(
                    refreshed_promo,
                    "before click",
                )
                state, board = await _click_promotion_with_recovery(
                    tab,
                    promotion_point,
                    promotion_state,
                    promotion_board,
                    session.resolved_color,
                    best_move,
                )
                ply = len(board.move_stack)
            session.set_pending(
                ply=ply,
                deadline=time.monotonic() + CLICK_ACK_TIMEOUT_S,
                move=best_move,
                url=state["url"],
            )
            print(f"[move] clicked {best_move}; waiting for board acknowledgement", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Play a chess.com game w/ Stockfish + CDP.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("-v", "--version", action="version", version=VERSION_TEXT)
    parser.add_argument("--dry-run", action="store_true",
                        help="pick and time moves but do not click them into the game")
    parser.add_argument("--color", choices=("auto", "white", "black"), default="auto",
                        help="side to play; auto reads the board orientation, which chess.com "
                             "always sets to your side (read-only DOM, no tampering)")
    args = parser.parse_args()
    color = None if args.color == "auto" else (chess.BLACK if args.color == "black" else chess.WHITE)
    with StockfishPolicy(CONFIG.stockfish_path, CONFIG.multipv, CONFIG.movetime_ms) as policy:
        asyncio.run(play(policy, color=color, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
