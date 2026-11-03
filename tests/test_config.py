import re

from chessbot.config import CONFIG


def test_config_loads():
    assert CONFIG.multipv == 4
    assert CONFIG.stockfish_path.endswith("stockfish.exe")


def test_watch_url_regex_covers_game_entry_routes():
    urls = (
        "https://www.chess.com/home",
        "https://www.chess.com/play",
        "https://www.chess.com/play/",
        "https://www.chess.com/play/online",
        "https://www.chess.com/play/online/new?action=createLiveChallenge",
        "https://www.chess.com/game/live/123",
    )
    assert all(re.search(CONFIG.watch_url_regex, url) for url in urls)
