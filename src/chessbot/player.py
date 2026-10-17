"""Watch a chess.com game tab, pick Stockfish moves, play them with humanized timing."""
import argparse
import asyncio

import chess

from chessbot.cdp import Tab, find_tab
from chessbot.config import CONFIG
from chessbot.board_reader import moves_to_board
from chessbot.clock import read_clock_ms
from chessbot.engine import StockfishPolicy
from chessbot.humanizer import think_time_ms
from chessbot.mover import square_to_xy

GET_STATE_JS = """
(() => {
  const board = document.querySelector('%s') || document.querySelector('%s');
  if (!board) return null;
  const r = board.getBoundingClientRect();
  const nodes = document.querySelectorAll('%s');
  const alt = document.querySelectorAll('%s');
  const container = nodes.length ? nodes : alt;
  const moves = [...container].map(n => n.textContent.trim()).join(' ');
  return { rect: [r.x, r.y, r.width, r.height], moves, cls: String(board.className), url: location.href };
})()
""" % (CONFIG.board_selector, CONFIG.board_fallback, CONFIG.move_node_selector, CONFIG.move_node_alt)


async def play(policy, color=chess.WHITE, dry_run=False, poll_s=0.4):
    ws = find_tab(CONFIG.cdp_url, CONFIG.game_url_regex)
    assert ws, "no chess.com game tab - open a live game first"
    async with Tab(ws) as tab:
        last_played = -1
        low_score_turns = 0
        while True:
            state = await tab.eval_js(GET_STATE_JS)
            if not state:
                await asyncio.sleep(2); continue
            try:
                board = moves_to_board(state["moves"])
            except ValueError as e:
                print(f"[board] {e} - retrying next poll"); await asyncio.sleep(poll_s); continue
            if board.is_game_over():
                print(f"game over: {state['url']}"); return
            my_turn = board.turn == color
            if not my_turn or len(board.move_stack) <= last_played:
                await asyncio.sleep(poll_s); continue
            remaining_ms = await read_clock_ms(tab) or 180_000  # fallback if selector unverified
            ranked = policy.analyse(board)
            if not ranked:
                await asyncio.sleep(poll_s); continue
            best_move, best_score = ranked[0]
            # resign rail: 3 consecutive turns below threshold
            low_score_turns = low_score_turns + 1 if best_score < CONFIG.resign_below_cp else 0
            if low_score_turns >= 3:
                print(f"resigning at ply {len(board.move_stack)} (score {best_score})"); return
            think_ms = think_time_ms(remaining_ms, CONFIG.think_median_ms, CONFIG.think_sigma,
                                     CONFIG.move_min_ms, CONFIG.max_clock_fraction)
            print(f"ply {len(board.move_stack) + 1}: {best_move} (score {best_score}, clock {remaining_ms}ms) thinking {think_ms}ms")
            await asyncio.sleep(think_ms / 1000)
            if dry_run:
                last_played = len(board.move_stack); continue
            rect = tuple(state["rect"]); white_bottom = "flipped" not in state["cls"]
            x1, y1 = square_to_xy(chess.square_name(best_move.from_square), rect, white_bottom)
            x2, y2 = square_to_xy(chess.square_name(best_move.to_square), rect, white_bottom)
            await tab.click(x1, y1); await asyncio.sleep(0.15); await tab.click(x2, y2)
            await asyncio.sleep(0.5)
            promo = await tab.eval_js(f"(() => {{ const el = document.querySelector(\"{CONFIG.promotion_selector}\"); if (!el) return null; const r = el.getBoundingClientRect(); return JSON.stringify([r.x + r.width/2, r.y + r.height/2]); }})()")
            if promo:
                px, py = (float(v) for v in promo.strip('[]').split(','))
                await tab.click(px, py)  # trusted CDP click, NOT DOM .click()
            last_played = len(board.move_stack)


def main():
    parser = argparse.ArgumentParser(description="Play a live chess.com game via Stockfish + CDP.")
    parser.add_argument("--dry-run", action="store_true",
                        help="pick and time moves but do not click them into the game")
    parser.add_argument("--color", choices=("white", "black"), default="white",
                        help="which side this bot plays (default: white)")
    args = parser.parse_args()
    color = chess.BLACK if args.color == "black" else chess.WHITE
    with StockfishPolicy(CONFIG.stockfish_path, CONFIG.multipv, CONFIG.movetime_ms) as policy:
        asyncio.run(play(policy, color=color, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
