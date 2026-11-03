"""Command-line entry point for Chessbot."""

from pathlib import Path
import sys

_SRC = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(_SRC))

from chessbot.player import main


if __name__ == "__main__":
    main()
