from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]  # chessbot/ (config.py is src/chessbot/config.py)


@dataclass(frozen=True)
class Config:
    # CDP
    cdp_url: str = "http://127.0.0.1:9222"
    watch_url_regex: str = (
        r"^https://www\.chess\.com/(?:"
        r"home(?:[/?#].*)?|"
        r"play(?:[/?#].*)?|"
        r"game/(?:(?:live|gambit)/)?\d+/?(?:[?#].*)?"
        r")$"
    )
    game_url_regex: str = r"^https://www\.chess\.com/game/(?:(?:live|gambit)/)?\d+/?(?:[?#].*)?$"

    # Selectors
    board_selector: str = "wc-chess-board"
    board_fallback: str = "#board-layout-chessBoard"
    move_node_selector: str = ".node.main-line-ply"
    move_node_alt: str = "[data-node]"
    promotion_selector: str = "[class*='promotion-piece-queen']"
    game_over_selector: str = (
        "game-over-modal, wc-game-over-modal, "
        "[data-cy='game-over-modal'], [class*='game-over-modal']"
    )
    game_result_selector: str = (
        "[data-cy='game-result'], [class*='game-over-header'], "
        "[class*='game-over-message'], [class*='result']"
    )

    # Engine
    stockfish_path: str = str(_ROOT / "bin" / "stockfish.exe")
    multipv: int = 4
    movetime_ms: int = 800

    # Humanizer
    think_median_ms: int = 2600
    think_sigma: float = 0.9
    max_clock_fraction: float = 0.06
    move_min_ms: int = 700
    sample_temperature_cp: int = 35

    # Safety
    resign_below_cp: int = -900
    min_move_number: int = 1


CONFIG = Config()
