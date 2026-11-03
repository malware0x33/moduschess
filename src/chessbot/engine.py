"""MultiPV analysis with ranked (move, score) output."""

import chess
import chess.engine


class StockfishPolicy:
    """Wraps the Stockfish UCI binary.

    One process per instance; call quit() when done (or use as context manager).
    analyse() returns [(move, score_cp_int)] best-first, up to multipv entries.
    pick() returns the same moves as a flat list, best-first. Move SAMPLING
    (choosing a suboptimal move by temperature) happens in player.py, not here.

    Contract: the underlying SimpleEngine is thread safe, but an overlapping
    analyse() CANCELS the previous command, never call analyse()
    concurrently, and do NOT mutate the board while analyse() is running.
    analyse() returns [] for a game-over board.

    Score convention
    (mate_score=10000): mate in N > 10000-N (mate in 1 = 9999), mated-in-N
    -> -10000+N, so downstream softmax samplers must clamp the gap (e.g. vs
    config.sample_temperature_cp=35, exp overflows beyond ~709 cp delta).
    """

    def __init__(self, path: str, multipv: int = 4, movetime_ms: int = 800):
        self._engine = chess.engine.SimpleEngine.popen_uci(path)
        try:
            self._engine.configure({"Threads": 2, "Hash": 128})
        except BaseException:
            self._engine.quit()  # don't leak the popped process on failed setup
            raise
        self.multipv = multipv
        self.movetime = movetime_ms

    def analyse(self, board: chess.Board) -> list[tuple[chess.Move, int]]:
        """MultiPV search [(move, score_int)] best first, [] if game over."""
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
        # emitted nonmonotonic (scores from different search depths); the
        # contract is best first, so enforce it (stable: ties keep engine rank).
        ranked.sort(key=lambda move_score: move_score[1], reverse=True)
        return ranked

    def pick(self, board: chess.Board) -> list[chess.Move]:
        """Return the analyse() moves as a flat list, best-first."""
        return [move for move, _ in self.analyse(board)]

    def quit(self) -> None:
        """Terminate the engine process. Single use: a second call raises."""
        self._engine.quit()

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        try:
            self.quit()
        except chess.engine.EngineError:
            pass  # already terminated (explicit quit() or engine crash)
