"""Minimal CDP client: attach to a Chrome tab, evaluate JS, dispatch clicks."""

import asyncio
import json
import re
import urllib.error
import urllib.request

import websockets

RPC_TIMEOUT_S = 30


class Tab:
    """A websocket connection to a single Chrome tab's CDP endpoint.

    Contract: use one Tab sequentially from a single async task. Concurrent
    _rpc calls would cross-steal each other's responses, because responses
    are only matched against the most recently sent request id.
    """

    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self._ws = None
        self._id = 0

    async def __aenter__(self) -> "Tab":
        self._ws = await websockets.connect(self.ws_url, max_size=50_000_000)
        return self

    async def __aexit__(self, *exc):
        await self._ws.close()

    async def _rpc(self, method: str, params: dict | None = None):
        """Send one CDP command and return its matching result object.

        Sequential calls only (see Tab docstring); protocol event frames
        (messages without an id) are skipped. Raises RuntimeError on a CDP
        error response, or RuntimeError("CDP RPC timed out: ...") if no
        matching response arrives within RPC_TIMEOUT_S seconds.
        """
        self._id += 1
        await self._ws.send(json.dumps({"id": self._id, "method": method, "params": params or {}}))
        try:
            async with asyncio.timeout(RPC_TIMEOUT_S):
                while True:
                    msg = json.loads(await self._ws.recv())
                    if msg.get("id") == self._id:
                        if "error" in msg:
                            raise RuntimeError(f"CDP error: {msg['error']}")
                        return msg.get("result", {})
        except asyncio.TimeoutError:
            raise RuntimeError(f"CDP RPC timed out: {method}") from None

    async def eval_js(self, expression: str):
        """Evaluate JS in the tab and return its JSON-serialised value.

        Raises RuntimeError if the evaluation throws, via the
        exceptionDetails CDP reports inside the Runtime.evaluate result.
        """
        res = await self._rpc(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        if res.get("exceptionDetails"):
            raise RuntimeError(
                f"eval_js failed: "
                f"{res['exceptionDetails'].get('exception', {}).get('description') or res['exceptionDetails']}"
            )
        return res.get("result", {}).get("value")

    async def click(self, x: float, y: float):
        """Dispatch a left-button press+release at viewport coords (x, y)."""
        for t in ("mousePressed", "mouseReleased"):
            await self._rpc(
                "Input.dispatchMouseEvent",
                {"type": t, "x": x, "y": y, "button": "left", "clickCount": 1},
            )


def find_tab(devtools_url: str, url_regex: str) -> str | None:
    """Return the webSocketDebuggerUrl of the first page tab matching url_regex."""
    url = devtools_url.rstrip("/") + "/json"
    try:
        tabs = json.loads(urllib.request.urlopen(url, timeout=5).read())
    except urllib.error.URLError as e:
        raise RuntimeError(
            "cannot reach Chrome devtools - is Chrome running with --remote-debugging-port=9222?"
        ) from e
    for t in tabs:
        ws_url = t.get("webSocketDebuggerUrl")
        if t.get("type") == "page" and ws_url and re.search(url_regex, t.get("url", "")):
            return ws_url
    return None
