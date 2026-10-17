from chessbot.mover import square_to_xy

def test_white_perspective():
    x, y = square_to_xy("a1", rect=(0, 0, 800, 800), white_bottom=True)
    assert (x, y) == (50, 750)
    x, y = square_to_xy("h8", rect=(0, 0, 800, 800), white_bottom=True)
    assert (x, y) == (750, 50)

def test_black_perspective():
    x, y = square_to_xy("a1", rect=(0, 0, 800, 800), white_bottom=False)
    assert (x, y) == (750, 50)
