"""Parse a chess.com DOM move list into a python-chess board."""
import re

import chess

SAN_RE = re.compile(
    r"\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|[O0]-[O0](?:-[O0])?[+#]?)(?![\w=+#])"
)

def extract_moves(html: str) -> list[str]:
    """Strip HTML tags and return the SAN tokens found, in order."""
    return SAN_RE.findall(re.sub(r"<[^>]+>", " ", html))

def moves_to_board(html: str) -> chess.Board:
    """Replay the SAN tokens in *html* onto a fresh board.

    Raises ValueError on unparseable/illegal input (e.g. a stale or
    mid-update DOM read); callers may retry on a fresh read.
    """
    board = chess.Board()
    for index, san in enumerate(extract_moves(html)):
        if re.fullmatch(r"[O0]-[O0](?:-[O0])?[+#]?", san):
            san = san.replace("0", "O")
        try:
            board.push_san(san)
        except ValueError as e:
            raise ValueError(
                f"bad SAN {san!r} at ply {index} (stale/mid-update DOM read?): {e}"
            ) from e
    return board
