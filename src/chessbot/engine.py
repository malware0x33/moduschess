"""Stockfish move policy: MultiPV analysis with ranked (move, score) output."""

import chess
import chess.engine


class StockfishPolicy:
    """Wraps the vendored Stockfish UCI binary.

    One process per instance; call quit() when done (or use as context manager).
    analyse() returns [(move, score_cp_int)] best-first, up to multipv entries.
    pick() returns the same moves as a flat list, best-first. Move SAMPLING
    (choosing a suboptimal move by temperature) happens in player.py, not here.
    """

    def __init__(self, path: str, multipv: int = 4, movetime_ms: int = 800):
        self._engine = chess.engine.SimpleEngine.popen_uci(path)
        self._engine.configure({"Threads": 2, "Hash": 128})
        self.multipv = multipv
        self.movetime = movetime_ms

    def analyse(self, board: chess.Board) -> list[tuple[chess.Move, int]]:
        infos = self._engine.analyse(
            board,
            chess.engine.Limit(time=self.movetime / 1000),
            multipv=self.multipv,
        )
        if isinstance(infos, dict):  # multipv=1 returns a dict
            infos = [infos]
        ranked = [
            (i["pv"][0], i["score"].pov(board.turn).score(mate_score=10000))
            for i in infos
            if i.get("pv")
        ]
        # At very short movetimes the engine's final MultiPV batch can be
        # emitted non-monotonic (scores from different search depths); the
        # contract is best-first, so enforce it (stable: ties keep engine rank).
        ranked.sort(key=lambda move_score: move_score[1], reverse=True)
        return ranked

    def pick(self, board: chess.Board) -> list[chess.Move]:
        return [move for move, _ in self.analyse(board)]

    def quit(self):
        self._engine.quit()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.quit()
