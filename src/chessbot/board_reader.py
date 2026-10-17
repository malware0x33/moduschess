import re
import chess

SAN_RE = re.compile(r"\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O-O|O-O)\b")

def extract_moves(html: str) -> list[str]:
    return SAN_RE.findall(re.sub(r"<[^>]+>", " ", html))

def moves_to_board(html: str) -> chess.Board:
    board = chess.Board()
    for san in extract_moves(html):
        board.push_san(san)
    return board
