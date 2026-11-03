# ModusChess Changelog

## Version 1.0.0

ModusChess v1.0.0 introduces a state-aware Chess.com player driven by
Stockfish and the Chrome DevTools Protocol.

### Browser connectivity

- Added support for Chrome's standard `/json` CDP discovery endpoint.
- Added support for Chrome 144+ permission-based remote debugging.
- Connects to the user's existing Chrome profile through
  `DevToolsActivePort`.
- Uses browser-level target discovery and flattened target sessions.
- Restricts automatic default-profile discovery to local loopback
  connections.
- Preserves compatibility with command-line remote-debugging sessions.
- Added clear connection, permission, and missing-tab status messages.

### Chess.com navigation awareness

- Added awareness for:
  - `/home`
  - `/play`
  - All `/play/*` routes
  - `/play/online`
  - `/play/online/new?...`
  - Supported numeric live-game URLs
- Chessbot can start before a game exists.
- Remains attached while the selected tab navigates between Home, Play,
  matchmaking, and game pages.
- Waits without repeatedly printing duplicate status messages.
- Begins game processing only when both a supported game URL and visible
  board are present.

### Game lifecycle state

- Added explicit lifecycle states:
  - `WAITING_FOR_GAME`
  - `PLAYING`
  - `GAME_FINISHED`
- Added a dedicated `PlayerState` model.
- Resets color, move acknowledgement, evaluation, and timing state for each
  new game.
- Reports a completed game once and waits for the next game without
  restarting.
- Prevents completed games from being processed repeatedly.

### Game completion and results

- Detects checkmate, stalemate, insufficient material, and other forced
  terminal board states through `python-chess`.
- Detects visible Chess.com result dialogs for:
  - Resignation
  - Timeout
  - Abandonment
  - Agreed draws
- Reads and normalizes result text from the game-over interface.
- Falls back to the board-derived outcome when result text is unavailable.
- Clears pending move state when a game finishes.

### Board and page-state reading

- Added a dedicated browser-state module.
- Added an atomic browser snapshot schema.
- Reads page URL, board availability, orientation, moves, result state, and
  game-over text in one snapshot.
- Added open Shadow DOM traversal for modern Chess.com components.
- Added primary and fallback board selectors.
- Added primary and fallback move-list selectors.
- Rebuilds piece letters from figurine-based move markup.
- Validates parsed move counts against DOM move-node counts.
- Retries safely when the board or move list is incomplete.

### Move handling

- Added board-orientation-aware square-to-screen mapping.
- Added trusted CDP mouse movement, press, and release events.
- Added randomized pointer offsets and pick-to-drop timing.
- Added queen-promotion selection through Shadow DOM-aware lookup.
- Revalidates the page URL, position, turn, and move legality after thinking.
- Replans when the position changes during calculation.
- Waits for the move list to acknowledge every submitted move.
- Rejects unexpected moves and stale page transitions.
- Stops when move acknowledgement exceeds the configured timeout.

### Side and clock detection

- Added automatic player-color detection from board orientation.
- Supports explicit `white`, `black`, and `auto` color selection.
- Resolves automatic color only after the game begins.
- Reads the selected side's clock rather than an arbitrary clock.
- Supports:
  - `m:ss`
  - `h:mm:ss`
  - Decimal low-time values such as `9.8`
  - Decimal values such as `0:09.8`
- Preserves a controlled fallback when the clock cannot be read.

### Stockfish integration

- Bundled Stockfish 19 for Windows.
- Added guarded Stockfish startup and shutdown.
- Added ranked MultiPV analysis.
- Enforces best-first result ordering.
- Converts mate scores into stable integer values.
- Supports configurable:
  - Engine path
  - MultiPV count
  - Analysis time
- Added weighted candidate sampling using centipawn temperature.
- Added a three-turn low-evaluation stop rail.

### Timing

- Added clock-aware randomized think times.
- Uses a log-normal timing distribution.
- Applies a configurable minimum delay.
- Caps delay to a configurable fraction of remaining clock time.
- Handles very short clocks without exceeding the calculated cap.

### Command-line interface

- Added root-level `main.py`.
- Added direct `src` package loading without editable installation.
- Added:
  - `--dry-run`
  - `--color auto`
  - `--color white`
  - `--color black`
  - `-v`
  - `--version`
- Version output:
  - Version 1.0.0
  - Written by J A G
  - Join Discord: https://discord.gg/h658Sa3sx
- Version output exits before launching Stockfish or connecting to Chrome.

### Configuration and documentation

- Added detailed configuration documentation.
- Documented runtime settings, defaults, units, selectors, and effects.
- Added installation, browser setup, usage, testing, and troubleshooting
  documentation.
- Added `requirements.txt` for standard `pip` installation.
- Removed `pyproject.toml`, `uv.lock`, and the `uv` build workflow.
- Added root ignore rules for `/tests/` and `/pytest.ini`.

### Testing

- Final verification: 75 tests passed.

### Release information

Written by J A G

Version 1.0.0

Discord https://discord.gg/h658Sa3sx
