"""Parse chess.com clock text and read a specific colour's clock via CDP."""

from decimal import Decimal, InvalidOperation

import chess

from chessbot.cdp import SHADOW_QUERY_JS


def clock_js(color: chess.Color) -> str:
    """Return JS that reads the clock timer."""
    side = "white" if color == chess.WHITE else "black"
    return """(() => {
%s
  const root = queryDeep('.clock-component.clock-%s');
  const el = root && queryDeep('[role="timer"], .clock-time-monospace, .clock-time', root);
  return el?.textContent?.trim() ?? null;
})()""" % (SHADOW_QUERY_JS, side)


def parse_clock_ms(text: str) -> int | None:
    """milliseconds for a chess clock string, or ``None``.

    Accepts ``m:ss``, ``h:mm:ss``, and low-time decimal seconds such as
    ``9.8`` or ``0:09.8``. Minutes/seconds must remain below 60.
    """
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) == 1:
        try:
            seconds = Decimal(parts[0])
        except InvalidOperation:
            return None
        if not seconds.is_finite():
            return None
        return int(seconds * 1000) if 0 <= seconds < 60 else None
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts[:-1]):
        return None
    try:
        seconds = Decimal(parts[-1])
    except InvalidOperation:
        return None
    if not seconds.is_finite():
        return None
    minutes = int(parts[-2])
    if not 0 <= seconds < 60 or minutes >= 60:
        return None
    hours = int(parts[0]) if len(parts) == 3 else 0
    return int((Decimal((hours * 60 + minutes) * 60) + seconds) * 1000)


async def read_clock_ms(tab, color: chess.Color):
    """read colors clock text from the game tab via CDP, in ms."""
    text = await tab.eval_js(clock_js(color))
    return parse_clock_ms(text) if text else None
