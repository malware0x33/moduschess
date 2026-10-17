"""Parse chess.com clock text ("m:ss" / "h:mm:ss") and read the clock via CDP."""

CLOCK_JS = """(() => {
  const el = document.querySelector('.clock-component .clock-time, [class*="clock-component"] [class*="time"]');
  return el ? el.textContent.trim() : null;
})()"""


def parse_clock_ms(text: str) -> int | None:
    """Return milliseconds for a "m:ss" or "h:mm:ss" clock string, or None.

    Rules: strip whitespace; split on ":"; all components must be digits;
    seconds < 60 and minutes < 60; empty/garbage -> None.
    """
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
        return None
    nums = [int(p) for p in parts]
    seconds = nums[-1]
    minutes = nums[-2] if len(nums) >= 2 else 0
    if seconds >= 60 or minutes >= 60:
        return None
    hours = nums[0] if len(nums) == 3 else 0
    return ((hours * 60 + minutes) * 60 + seconds) * 1000


async def read_clock_ms(tab):
    """Read the opponent/own clock text from the game tab via CDP, in ms.

    # TODO(live-verify): selector is a best-guess placeholder; live
    # verification happens in Task 9.
    """
    text = await tab.eval_js(CLOCK_JS)
    return parse_clock_ms(text) if text else None
