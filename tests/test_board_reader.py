from chessbot.board_reader import moves_to_board

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
