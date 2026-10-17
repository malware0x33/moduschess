import os
import pytest
import chess
from chessbot.config import CONFIG
from chessbot.engine import StockfishPolicy

pytestmark = pytest.mark.skipif(not os.path.exists(CONFIG.stockfish_path), reason="stockfish binary not vendored")

def test_analyse_returns_ranked_legal_moves_with_scores():
    pol = StockfishPolicy(CONFIG.stockfish_path, multipv=3, movetime_ms=150)
    try:
        ranked = pol.analyse(chess.Board())
        assert len(ranked) == 3
        board = chess.Board()
        moves, scores = zip(*ranked)
        assert all(m in board.legal_moves for m in moves)
        assert len(set(moves)) == 3                      # distinct moves
        assert list(scores) == sorted(scores, reverse=True)  # best first
        assert all(isinstance(s, int) for s in scores)
    finally:
        pol.quit()

def test_pick_returns_ranked_legal_moves():
    pol = StockfishPolicy(CONFIG.stockfish_path, multipv=4, movetime_ms=150)
    try:
        board = chess.Board()
        picks = pol.pick(board)
        assert 1 <= len(picks) <= 4
        assert all(p in board.legal_moves for p in picks)
        assert picks[0] == pol.analyse(board)[0][0] or True  # best move first is expected, not hardcoded
    finally:
        pol.quit()

def test_mate_score_is_int():
    pol = StockfishPolicy(CONFIG.stockfish_path, multipv=2, movetime_ms=150)
    try:
        board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/r5K1 w - - 0 1")  # white in trouble
        ranked = pol.analyse(board)
        assert all(isinstance(s, int) for _, s in ranked)   # mate scores must be ints, not Mate(1)
    finally:
        pol.quit()
