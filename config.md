CHESSBOT CONFIGURATION REFERENCE
================================

This file documents every field in src\chessbot\config.py. It is not parsed
by Chessbot and changing it has no runtime effect. To change a setting, edit
the corresponding default in the Config dataclass, preserve its Python type,
and restart Chessbot.

Actual configuration source:

    src\chessbot\config.py


CDP SETTINGS
------------

cdp_url
    Default: "http://127.0.0.1:9222"
    Type: string URL

    Base URL of the browser's Chrome DevTools Protocol endpoint. Chessbot first
    requests <cdp_url>/json to enumerate tabs. If Chrome's default-profile
    permission mode deliberately returns HTTP 404, Chessbot instead reads the
    local Chrome Stable DevToolsActivePort file, connects to its browser
    WebSocket, discovers page targets, and attaches a flattened session to the
    matching tab. The fallback is accepted only for a loopback URL and only
    when the active port matches this setting. A trailing slash is allowed.

watch_url_regex
    Default:
        Home, the /play route family, and supported numeric game URLs
        under https://www.chess.com/
    Type: Python regular-expression string

    Selects which CDP page target Chessbot initially attaches to. It accepts
    /home, exact /play, every /play subroute (including /play/online/new with
    query parameters), and every URL accepted by game_url_regex. This lets
    Chessbot start before matchmaking or a game begins and remain attached
    while that tab navigates. If several tabs match, Chessbot uses the first
    one returned by Chrome.

game_url_regex
    Default:
        r"^https://www\.chess\.com/game/(?:(?:live|gambit)/)?\d+/?(?:[?#].*)?$"
    Type: Python regular-expression string

    Distinguishes an active-game URL from Home, Play Online, and matchmaking
    states after Chessbot has attached. The default accepts a numeric game URL
    with an optional live/ or gambit/ segment, optional trailing slash, and
    optional query text or fragment. Chessbot acts only when this pattern and
    a visible configured board are both present.


PAGE SELECTORS
--------------

All selectors below are CSS selectors. Chessbot searches the document and all
nested open shadow roots, so the selected elements do not have to live in the
top-level document.

board_selector
    Default: "wc-chess-board"
    Type: string CSS selector

    Primary selector for the visible game board. Its bounding rectangle is
    used to convert chess squares into viewport click coordinates. Its
    "flipped" class also determines board orientation when color is auto.

board_fallback
    Default: "#board-layout-chessBoard"
    Type: string CSS selector

    Secondary board selector used only when board_selector finds nothing.
    This provides compatibility with an alternate Chess.com board container.

move_node_selector
    Default: ".node.main-line-ply"
    Type: string CSS selector

    Primary selector for individual main-line move nodes. Chessbot reads their
    text in page order, normalizes whitespace and figurine markup, and rebuilds
    a python-chess Board from the resulting SAN move sequence.

move_node_alt
    Default: "[data-node]"
    Type: string CSS selector

    Fallback selector for move nodes. It is used only when
    move_node_selector returns no elements. A selector that also matches
    non-move elements can make the parsed move count disagree with the DOM and
    cause Chessbot to retry instead of acting.

promotion_selector
    Default: "[class*='promotion-piece-queen']"
    Type: string CSS selector

    Finds the queen option in a promotion chooser after Chessbot clicks a pawn
    onto the last rank. If present, Chessbot clicks the element's center. The
    default therefore promotes to a queen; it does not select an underpromotion
    piece based on the engine move.

game_over_selector
    Default:
        "game-over-modal, wc-game-over-modal, [data-cy='game-over-modal'],
        [class*='game-over-modal']"
    Type: comma-separated string of CSS selectors

    Finds a visible Chess.com game-over component, including outcomes that
    cannot be inferred from legal moves alone, such as resignation, timeout,
    abandonment, and agreed draws. Hidden matching elements are ignored.
    Forced terminal positions are also detected independently by python-chess.

game_result_selector
    Default:
        "[data-cy='game-result'], [class*='game-over-header'],
        [class*='game-over-message'], [class*='result']"
    Type: comma-separated string of CSS selectors

    Searches inside the visible game-over component for its result or summary
    text. Whitespace is normalized before the result is printed. When no text
    matches, Chessbot falls back to a python-chess result for forced terminal
    positions, or reports that the result is unavailable.


ENGINE SETTINGS
---------------

stockfish_path
    Default: <repository root>\bin\stockfish.exe
    Type: string filesystem path

    Path passed to python-chess when starting the UCI engine. The default is
    calculated from config.py's location, so it does not depend on the current
    working directory. The file must exist and be executable. Chessbot starts
    one Stockfish process and configures it with two threads and 128 MB of hash.

multipv
    Default: 4
    Type: positive integer candidate count

    Number of principal variations requested from Stockfish for each position.
    These candidates are ranked by score before move sampling. Larger values
    provide more alternatives but increase analysis work; 1 provides only the
    engine's leading move.

movetime_ms
    Default: 800
    Type: integer milliseconds

    Stockfish analysis time for each position. The value is converted to
    seconds for python-chess's engine limit. Increasing it normally improves
    search depth while delaying every decision and consuming more CPU time.


MOVE-TIMING AND SAMPLING SETTINGS
---------------------------------

think_median_ms
    Default: 2600
    Type: integer milliseconds

    Median of the log-normal distribution used to sample a pre-move think
    time. It is a target distribution parameter, not a guaranteed delay: the
    sampled time must also satisfy move_min_ms and max_clock_fraction.

think_sigma
    Default: 0.9
    Type: non-negative floating-point number

    Shape parameter (standard deviation in log space) for randomized think
    times. A larger value creates a wider and more variable distribution. A
    value near zero concentrates samples near think_median_ms.

max_clock_fraction
    Default: 0.06
    Type: floating-point fraction

    Hard cap on think time as a fraction of the bot's remaining clock. At the
    default, one delay may use at most 6 percent of the reported remaining
    time. The cap overrides move_min_ms when little time remains. If the page
    clock cannot be read, player.py substitutes 180,000 ms before applying this
    calculation.

move_min_ms
    Default: 700
    Type: integer milliseconds

    Normal lower bound for sampled think time. When the
    max_clock_fraction-derived cap is below this value, the cap wins and also
    becomes the effective lower bound, preventing the delay from exceeding the
    short remaining clock allowance.

sample_temperature_cp
    Default: 35
    Type: integer centipawns

    Controls weighted selection among the MultiPV candidates. Each candidate's
    weight is exp(-(best_score - candidate_score) / temperature). Lower values
    strongly favor the top engine move; higher values give inferior candidates
    more probability. The implementation treats values below 1 as 1 to avoid
    division by zero. Roughly 100 centipawns represent one pawn, while mating
    scores are mapped near +/-10,000.


SAFETY SETTINGS
---------------

resign_below_cp
    Default: -900
    Type: integer centipawns from the side-to-move perspective

    Evaluation threshold for the stop rail. When Stockfish's best score is
    below this value on three consecutive bot turns, Chessbot stops processing
    the game. Despite the setting's name, the current implementation does not
    click Chess.com's resign control; it only exits the player loop.

min_move_number
    Default: 1
    Type: integer move number

    Reserved setting that is currently not read by player.py or any other
    runtime module. Changing it has no effect in the current implementation.
    No minimum-move gate is presently enforced.


RELATED FIXED CONSTANTS
-----------------------

These behaviors are configurable only by editing their defining modules; they
are not fields of Config:

    CLICK_ACK_TIMEOUT_S = 5.0
        Defined in state.py and enforced by player.py. Maximum wait for the
        move list to acknowledge a click before Chessbot stops.

    RPC_TIMEOUT_S = 30
        Defined in cdp.py. Maximum wait for a matching CDP response.

    Stockfish Threads = 2; Hash = 128 MB
        Defined in engine.py when the UCI process is initialized.


VALIDATING CHANGES
------------------

After editing config.py, run:

    .\.venv\Scripts\python.exe -m pytest
    .\.venv\Scripts\python.exe .\main.py --help

Start with --dry-run when validating browser selectors, engine settings, or
timing changes so no board clicks are sent.
