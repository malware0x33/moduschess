from chessbot.config import CONFIG


def test_config_loads():
    assert CONFIG.multipv == 4
    assert CONFIG.stockfish_path.endswith("stockfish.exe")
