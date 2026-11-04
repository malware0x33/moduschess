"""Minimal CDP client: attach to a Chrome tab, evaluate JS, dispatch clicks."""

import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
import random
import re
import urllib.error
import urllib.parse
import urllib.request

import websockets

RPC_TIMEOUT_S = 30
SESSION_NOT_FOUND_CODE = -32001


class CDPError(RuntimeError):
    """A structured Chrome DevTools Protocol error response."""

    def __init__(self, error):
        self.error = error
        self.code = error.get("code") if isinstance(error, dict) else None
        super().__init__(f"CDP error: {error}")


@dataclass(frozen=True)
class BrowserConnection:
    """Browser-scoped WebSocket plus the page URL it should attach to."""

    ws_url: str
    url_regex: str


# Runtime.evaluate executes in the page's JavaScript context. Normal CSS
# selectors stop at a shadow boundary, so every DOM probe uses these helpers
# to traverse the document plus all nested *open* shadow roots.
SHADOW_QUERY_JS = """
  const collectRoots = (start = document) => {
    const roots = [start];
    if (start.shadowRoot) roots.push(start.shadowRoot);
    for (let index = 0; index < roots.length; index += 1) {
      for (const element of roots[index].querySelectorAll('*')) {
        if (element.shadowRoot) roots.push(element.shadowRoot);
      }
    }
    return roots;
  };
  const queryFirstFromRoots = (selector, roots) => {
    for (const root of roots) {
      const match = root.querySelector(selector);
      if (match) return match;
    }
    return null;
  };
  const queryAllFromRoots = (selector, roots) =>
    roots.flatMap(root => [...root.querySelectorAll(selector)]);
  const queryDeep = (selector, start = document) => {
    return queryFirstFromRoots(selector, collectRoots(start));
  };
  const queryAllDeep = (selector, start = document) =>
    queryAllFromRoots(selector, collectRoots(start));
"""


class Tab:
    """A direct tab connection or browser-scoped attached CDP session.

    Contract: use one Tab sequentially from a single async task. Concurrent
    _rpc calls would cross-steal each other's responses, because responses
    are only matched against the most recently sent request id.
    """

    def __init__(self, connection: str | BrowserConnection):
        if isinstance(connection, BrowserConnection):
            self.ws_url = connection.ws_url
            self._target_url_regex = connection.url_regex
        else:
            self.ws_url = connection
            self._target_url_regex = None
        self._ws = None
        self._id = 0
        self._session_id = None

    @property
    def supports_session_recovery(self) -> bool:
        """Return whether this tab uses a reattachable browser session."""
        return self._target_url_regex is not None

    async def __aenter__(self) -> "Tab":
        self._ws = await websockets.connect(self.ws_url, max_size=50_000_000)
        try:
            if self._target_url_regex is not None:
                await self._attach_matching_page(self._target_url_regex)
            return self
        except BaseException:
            await self._ws.close()
            self._ws = None
            raise

    async def __aexit__(self, *exc):
        if self._ws is not None:
            await self._ws.close()

    async def _attach_matching_page(self, url_regex: str) -> None:
        """Attach a flattened session to the first matching page target."""
        result = await self._rpc("Target.getTargets")
        target = next(
            (
                info
                for info in result.get("targetInfos", [])
                if info.get("type") == "page"
                and re.search(url_regex, info.get("url", ""))
            ),
            None,
        )
        if target is None:
            raise RuntimeError(
                "no matching Chess.com tab - open Home, Play, "
                "or a live game"
            )
        attached = await self._rpc(
            "Target.attachToTarget",
            {"targetId": target["targetId"], "flatten": True},
        )
        session_id = attached.get("sessionId")
        if not session_id:
            raise RuntimeError("Chrome did not return a CDP target session")
        self._session_id = session_id

    async def _rpc(self, method: str, params: dict | None = None):
        """Send one CDP command and return its matching result object.

        Sequential calls only (see Tab docstring); protocol event frames
        (messages without an id) are skipped. Raises RuntimeError on a CDP
        error response, or RuntimeError("CDP RPC timed out: ...") if no
        matching response arrives within RPC_TIMEOUT_S seconds.
        """
        self._id += 1
        request = {"id": self._id, "method": method, "params": params or {}}
        if self._session_id is not None:
            request["sessionId"] = self._session_id
        await self._ws.send(json.dumps(request))
        try:
            async with asyncio.timeout(RPC_TIMEOUT_S):
                while True:
                    msg = json.loads(await self._ws.recv())
                    if msg.get("id") == self._id:
                        if "error" in msg:
                            raise CDPError(msg["error"])
                        return msg.get("result", {})
        except asyncio.TimeoutError:
            raise RuntimeError(f"CDP RPC timed out: {method}") from None

    async def eval_js(self, expression: str):
        """Evaluate JS in the tab and return its JSON-serialised value.

        Raises RuntimeError if the evaluation throws, via the
        exceptionDetails CDP reports inside the Runtime.evaluate result.
        """
        params = {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        }
        try:
            res = await self._rpc("Runtime.evaluate", params)
        except CDPError as error:
            if (
                error.code != SESSION_NOT_FOUND_CODE
                or not self.supports_session_recovery
                or self._session_id is None
            ):
                raise

            # A flattened target session can disappear while the browser-level
            # WebSocket remains healthy. Reattach without the stale session id
            # and replay only this read-only evaluation once. Input commands
            # deliberately do not use this recovery path.
            self._session_id = None
            await self._attach_matching_page(self._target_url_regex)
            res = await self._rpc("Runtime.evaluate", params)
        if res.get("exceptionDetails"):
            raise RuntimeError(
                f"eval_js failed: "
                f"{res['exceptionDetails'].get('exception', {}).get('description') or res['exceptionDetails']}"
            )
        return res.get("result", {}).get("value")

    async def click(self, x: float, y: float):
        """Dispatch a trusted hover+press+release at viewport coords (x, y).

        A small per-click offset keeps repeated clicks off the exact same
        pixel (a human never clicks identical coordinates twice), and a
        mouseMoved precedes every press the way real pointer input does.
        """
        x += random.uniform(-8.0, 8.0)
        y += random.uniform(-8.0, 8.0)
        await self._rpc(
            "Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}
        )
        for t in ("mousePressed", "mouseReleased"):
            await self._rpc(
                "Input.dispatchMouseEvent",
                {"type": t, "x": x, "y": y, "button": "left", "clickCount": 1},
            )


def _devtools_active_port_path() -> Path:
    """Return Chrome Stable's permission-mode endpoint file on Windows."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError(
            "LOCALAPPDATA is unavailable; cannot locate Chrome's "
            "DevToolsActivePort file"
        )
    return (
        Path(local_app_data)
        / "Google"
        / "Chrome"
        / "User Data"
        / "DevToolsActivePort"
    )


def _permission_browser_connection(
    devtools_url: str,
    url_regex: str,
) -> BrowserConnection:
    """Build a browser connection from Chrome's permission-mode endpoint."""
    parsed = urllib.parse.urlparse(devtools_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise RuntimeError(
            "Chrome's default-profile connection is supported only for a "
            "local loopback CDP URL"
        )
    expected_port = parsed.port or (443 if parsed.scheme == "https" else 80)
    active_port_path = _devtools_active_port_path()
    try:
        lines = active_port_path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        raise RuntimeError(
            "Chrome's HTTP endpoint is hidden and DevToolsActivePort could not "
            "be read; enable Remote debugging at "
            "chrome://inspect/#remote-debugging"
        ) from e
    if len(lines) < 2:
        raise RuntimeError("Chrome's DevToolsActivePort file is incomplete")
    try:
        reported_port = int(lines[0].strip())
    except ValueError as e:
        raise RuntimeError(
            "Chrome's DevToolsActivePort contains an invalid port"
        ) from e
    if reported_port != expected_port:
        raise RuntimeError(
            f"Chrome's DevToolsActivePort reports port {reported_port}, "
            f"but Chessbot is configured for {expected_port}"
        )
    browser_path = lines[1].strip()
    if not browser_path.startswith("/devtools/browser/"):
        raise RuntimeError(
            "Chrome's DevToolsActivePort contains an invalid WebSocket path"
        )
    ws_scheme = "wss" if parsed.scheme == "https" else "ws"
    host = parsed.hostname
    if ":" in host:
        host = f"[{host}]"
    return BrowserConnection(
        ws_url=f"{ws_scheme}://{host}:{reported_port}{browser_path}",
        url_regex=url_regex,
    )


def find_tab(devtools_url: str, url_regex: str) -> str | BrowserConnection | None:
    """Find a page endpoint using legacy HTTP or Chrome permission mode."""
    url = devtools_url.rstrip("/") + "/json"
    try:
        tabs = json.loads(urllib.request.urlopen(url, timeout=5).read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return _permission_browser_connection(devtools_url, url_regex)
        raise RuntimeError(f"Chrome devtools returned HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            "cannot reach Chrome devtools - is Chrome running with --remote-debugging-port=9222?"
        ) from e
    for t in tabs:
        ws_url = t.get("webSocketDebuggerUrl")
        if t.get("type") == "page" and ws_url and re.search(url_regex, t.get("url", "")):
            return ws_url
    return None
