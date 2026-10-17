from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    cdp_url: str = "http://127.0.0.1:9222"
    game_url_regex: str = r"^https://www\.chess\.com/game/(live|gambit)/"
    board_selector: str = "wc-chess-board"
    board_fallback: str = "#board-layout-chessBoard"
    move_node_selector: str = "[data-ply]"
    move_node_alt: str = ".move-list .node"
    promotion_selector: str = "[class*='promotion-piece-queen']"
    stockfish_path: str = "bin/stockfish.exe"
    multipv: int = 4
    movetime_ms: int = 800
    think_median_ms: int = 2600
    think_sigma: float = 0.9
    max_clock_fraction: float = 0.06
    min_ms: int = 700
    sample_temperature_cp: int = 35
    resign_below_cp: int = -900
    min_move_number: int = 1

CONFIG = Config()
