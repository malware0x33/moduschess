import os
import pytest
import chess
from chessbot.config import CONFIG
from chessbot.engine import StockfishPolicy

pytestmark = pytest.mark.skipif(not os.path.exists(CONFIG.stockfish_path), reason="stockfish binary not vendored")

def test_analyse_returns_ranked_legal_moves_with_scores():
    with StockfishPolicy(CONFIG.stockfish_path, multipv=3, movetime_ms=150) as pol:
        ranked = pol.analyse(chess.Board())
        assert len(ranked) == 3
        board = chess.Board()
        moves, scores = zip(*ranked)
        assert all(m in board.legal_moves for m in moves)
        assert len(set(moves)) == 3                      # distinct moves
        assert list(scores) == sorted(scores, reverse=True)  # best first
        assert all(isinstance(s, int) for s in scores)

def test_pick_returns_ranked_legal_moves():
    with StockfishPolicy(CONFIG.stockfish_path, multipv=4, movetime_ms=150) as pol:
        board = chess.Board()
        ranked = pol.analyse(board)
        picks = [m for m, _ in ranked]
        assert 1 <= len(picks) <= 4
        assert all(p in board.legal_moves for p in picks)

def test_mate_score_converts_to_int():
    with StockfishPolicy(CONFIG.stockfish_path, multipv=2, movetime_ms=150) as pol:
        board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1")  # Re8# is mate in 1
        ranked = pol.analyse(board)
        assert ranked                                    # non-empty: engine reports a pv
        assert all(isinstance(s, int) for _, s in ranked)   # mate scores must be ints, not Mate(1)
        assert ranked[0][1] > 9000                       # mate-in-1 -> 10000 - 1 = 9999
