"""Minimal CDP client: attach to a Chrome tab, evaluate JS, dispatch clicks."""

import asyncio
import json
import re
import urllib.request

import websockets


class Tab:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self._id = 0

    async def __aenter__(self):
        self._ws = await websockets.connect(self.ws_url, max_size=50_000_000)
        return self

    async def __aexit__(self, *exc):
        await self._ws.close()

    async def _rpc(self, method: str, params: dict | None = None):
        self._id += 1
        await self._ws.send(json.dumps({"id": self._id, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(await self._ws.recv())
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise RuntimeError(f"CDP error: {msg['error']}")
                return msg.get("result", {})

    async def eval_js(self, expression: str):
        res = await self._rpc(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        return res.get("result", {}).get("value")

    async def click(self, x: float, y: float):
        for t in ("mousePressed", "mouseReleased"):
            await self._rpc(
                "Input.dispatchMouseEvent",
                {"type": t, "x": x, "y": y, "button": "left", "clickCount": 1},
            )


def find_tab(devtools_url: str, url_regex: str) -> str | None:
    """Return the webSocketDebuggerUrl of the first page tab matching url_regex."""
    tabs = json.loads(urllib.request.urlopen(f"{devtools_url}/json").read())
    for t in tabs:
        if t.get("type") == "page" and re.search(url_regex, t.get("url", "")):
            return t["webSocketDebuggerUrl"]
    return None
