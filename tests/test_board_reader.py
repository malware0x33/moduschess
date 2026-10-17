import pytest

from chessbot.board_reader import extract_moves, moves_to_board

HTML = '''
<div class="move-list">
  <div data-ply="1"><span>e4</span></div>
  <div data-ply="2"><span>e5</span></div>
  <div data-ply="3"><span>Nf3</span></div>
</div>'''

def test_moves_to_board():
    board = moves_to_board(HTML)
    assert board.fen() == "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2"

def test_empty():
    assert moves_to_board("<div></div>").fen().startswith("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w")

def test_castle_tokens():
    # I1/I2: all castle spellings must tokenize fully (0-0 was skipped).
    assert extract_moves("O-O O-O-O 0-0") == ["O-O", "O-O-O", "0-0"]
    # I4: check/mate suffixes must stay on castle tokens.
    assert extract_moves("O-O+") == ["O-O+"]
    assert extract_moves("O-O-O+") == ["O-O-O+"]
    assert extract_moves("O-O#") == ["O-O#"]
    assert extract_moves("0-0+") == ["0-0+"]

def test_castle_check_suffix_pushes():
    # I4: suffixed castles must tokenize fully, normalize 0->O (suffix kept), push.
    # Same line as test_zero_castle_pushes; suffixes don't change the moves.
    board = moves_to_board("e4 e5 Nf3 Nc6 Nc3 Nf6 Bb5 Bc5 O-O+ 0-0+")
    assert board.fen() == "r1bq1rk1/pppp1ppp/2n2n2/1Bb1p3/4P3/2N2N2/PPPP1PPP/R1BQ1RK1 w - - 8 6"

def test_zero_castle_pushes():
    # I2: 0-0 must normalize to O-O and push; rights end up "-" after both castle.
    board = moves_to_board("e4 e5 Nf3 Nc6 Nc3 Nf6 Bb5 Bc5 O-O 0-0")
    assert board.fen() == "r1bq1rk1/pppp1ppp/2n2n2/1Bb1p3/4P3/2N2N2/PPPP1PPP/R1BQ1RK1 w - - 8 6"

def test_promotion_suffix_tokenized_and_pushed():
    # I1: trailing \b used to drop the "+" from exd8=Q+.
    assert extract_moves("<span>exd8=Q+</span>") == ["exd8=Q+"]
    board = moves_to_board("f4 a6 f5 e6 fxe6 b6 e7 Nf6 exd8=Q+")
    assert board.fen() == "rnbQkb1r/2pp1ppp/pp3n2/8/8/8/PPPPP1PP/RNBQKBNR b KQkq - 0 5"

def test_mate_suffix_kept():
    # I1: '#' suffix must stay on the token.
    assert extract_moves("Qh4#") == ["Qh4#"]

def test_inline_move_numbers():
    # Guard: move numbers/dots interleaved must still yield clean SAN.
    assert extract_moves("1.e4 1...c5 2.Nf3") == ["e4", "c5", "Nf3"]

def test_bad_san_raises_with_context():
    # I3: stale/mid-update reads must surface ply + token, not a bare error.
    with pytest.raises(ValueError, match=r"bad SAN 'Ke5' at ply 2"):
        moves_to_board("e4 e5 Ke5")
