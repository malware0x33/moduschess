ModusChess watches a Chess.com tab from the Home or Play pages, detects when a live game begins reconstructs the position from the move list, asks
Stockfish for moves, waits for a "clock aware" randomised think time, and  plays a move through the Chrome DevTools Protocol (CDP). After a game ends it reports the result and waits for the next game.


Reqs:

- OS with Python 3.11 or newer.
- The Python dependencies listed in requirements.txt.
- Stockfish at bin\stockfish.exe. The executable is intentionally included as we wrap this; see bin\README.md for the vendored version and download details.
- Chrome or another Chromium browser exposing CDP at http://127.0.0.1:9222.
- An open Chess.com Home, Play, matchmaking, or live-game tab whose URL matches watch_url_regex as documented in config.md.


install:

From the root dir, create a virt environment:

- python -m venv .venv

Install the runtime dependencies:

- .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Confirm that the command-line entry point is available:

- .\.venv\Scripts\python.exe .\main.py --help


Starting the browser

To use the existing Chrome profile in Chrome 144 or newer:

1. Open chrome://inspect/#remote-debugging in Chrome.
2. Enable "Allow remote debugging for this browser instance".
3. Keep that Chrome instance open. Chessbot may be started while the tab is on Home or any Play page, before a game exists.
4. When Chessbot connects, approve Chrome's remote debugging permission prompt.

In this permission based mode, http://127.0.0.1:9222/json returns HTTP 404 by design. Modus detects that response and connects through Chrome's local DevToolsActivePort WebSocket instead. It does not require a separate profile.

Modus searches the available page targets and attaches to the first supported Chess.com Home, Play, matchmaking, or game URL.

Running modus:

Start click mode only when browser input is intended:

   - .\.venv\Scripts\python.exe main.py

Stop the process with Ctrl+C.

Command-line options:

    --dry-run
        Select and time moves, but do not click the board.

    --color auto
        Infer the bot's side once the game begins. This is the default.

    --color white
        Force Chessbot to play White.

    --color black
        Force Chessbot to play Black.

The console reports attachment, waiting, analysis, replanning, move acknowledgement, and game-over states. In click mode, Modus waits for the move list to confirm each submitted move and stops if confirmation fails. It detects forced board outcomes plus visible Chess.com result dialogs, reports each result once, and then waits for a different game URL.


config:

Runtime settings are defined by the Config dataclass in:

- src\chessbot\config.py

config.md explains every field, its default, units, and runtime effect. The config.md file is documentation only; changing it does not alter Modus

After changing config.py, restart Chessbot so module level settings and selectors are rebuilt.

Troubleshoot:

"cannot reach Chrome devtools"
    Chrome is not listening at the configured cdp_url. Enable remote debugging
    at chrome://inspect/#remote-debugging, use the command-line fallback above,
    or update cdp_url in config.py.

"DevToolsActivePort could not be read"
    Chrome returned HTTP 404 in permission mode, but Chessbot could not find
    the default-profile WebSocket information. Confirm remote debugging is
    enabled in Chrome Stable and that it reports server 127.0.0.1:9222.

"no matching Chess.com tab"
    CDP is reachable, but none of its page tabs match watch_url_regex. Open
    Chess.com Home, Play, matchmaking, or a supported live game in the
    same Chrome instance.

Chessbot remains on "no active game"
    The attached Home or Play tab has not navigated to a supported live
    game URL with a visible board. Start a game in that same tab. If a game is
    visible, verify game_url_regex and the configured board selectors.

Stockfish cannot be started
    Confirm that bin\stockfish.exe exists and can run on the machine. Restore
    it using bin\README.md if it is missing.

"move click was not acknowledged"
    The move list did not advance to the expected move within five seconds.
    Chessbot stops rather than risk clicking from stale state.

Written by J A G:
Version 1.0.0
Join discord: https://discord.gg/h658Sa3sx
