import asyncio
import json

import pytest

import chessbot.cdp as cdp


def _fake_urlopen(payload):
    class R:
        def read(self):
            return json.dumps(payload).encode()

    return R()


def test_find_tab_matches_page_url(monkeypatch):
    tabs = [
        {"type": "page", "url": "https://www.chess.com/today", "webSocketDebuggerUrl": "ws://x/1"},
        {"type": "page", "url": "https://www.chess.com/game/live/123", "webSocketDebuggerUrl": "ws://x/2"},
        {"type": "iframe", "url": "https://www.chess.com/game/live/999", "webSocketDebuggerUrl": "ws://x/3"},
        {"type": "page", "url": "https://www.chess.com/game/live/555"},
    ]
    monkeypatch.setattr(cdp.urllib.request, "urlopen", lambda url, timeout=None: _fake_urlopen(tabs))
    assert cdp.find_tab("http://127.0.0.1:9222", r"chess\.com/game/") == "ws://x/2"


def test_find_tab_no_match_returns_none(monkeypatch):
    monkeypatch.setattr(cdp.urllib.request, "urlopen", lambda url, timeout=None: _fake_urlopen([]))
    assert cdp.find_tab("http://127.0.0.1:9222", r"chess\.com") is None


def test_find_tab_falls_back_to_default_profile_browser_socket(
    monkeypatch, tmp_path
):
    active_port = tmp_path / "DevToolsActivePort"
    active_port.write_text(
        "9222\n/devtools/browser/permission-token\n",
        encoding="utf-8",
    )

    def hidden_http_endpoint(url, timeout=None):
        raise cdp.urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    monkeypatch.setattr(cdp.urllib.request, "urlopen", hidden_http_endpoint)
    monkeypatch.setattr(cdp, "_devtools_active_port_path", lambda: active_port)

    connection = cdp.find_tab(
        "http://127.0.0.1:9222",
        r"chess\.com/game/",
    )

    assert connection == cdp.BrowserConnection(
        ws_url="ws://127.0.0.1:9222/devtools/browser/permission-token",
        url_regex=r"chess\.com/game/",
    )


def test_default_profile_fallback_rejects_a_different_active_port(
    monkeypatch, tmp_path
):
    active_port = tmp_path / "DevToolsActivePort"
    active_port.write_text(
        "9333\n/devtools/browser/permission-token\n",
        encoding="utf-8",
    )

    def hidden_http_endpoint(url, timeout=None):
        raise cdp.urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    monkeypatch.setattr(cdp.urllib.request, "urlopen", hidden_http_endpoint)
    monkeypatch.setattr(cdp, "_devtools_active_port_path", lambda: active_port)

    with pytest.raises(RuntimeError, match="reports port 9333.*configured for 9222"):
        cdp.find_tab("http://127.0.0.1:9222", r"chess\.com/game/")


class FakeWs:
    """Async websocket double: replies with an event frame, then the response."""

    def __init__(self, exc=False):
        self.sent, self.exc, self._recvs = [], exc, 0

    async def send(self, raw):
        self.sent.append(json.loads(raw))

    async def recv(self):
        self._recvs += 1
        if self._recvs == 1:
            return json.dumps({"method": "Page.frameStartedLoading", "params": {}})
        req = self.sent[-1]
        if self.exc:
            frame = {"id": req["id"], "result": {"exceptionDetails": {"exception": {"description": "SyntaxError: boom"}}}}
        else:
            frame = {"id": req["id"], "result": {"result": {"value": 42}}}
        return json.dumps(frame)

    async def close(self):
        pass


class FakeBrowserWs:
    """Browser-scoped CDP double for target discovery and attachment."""

    def __init__(self):
        self.sent = []
        self.closed = False

    async def send(self, raw):
        self.sent.append(json.loads(raw))

    async def recv(self):
        request = self.sent[-1]
        method = request["method"]
        if method == "Target.getTargets":
            result = {
                "targetInfos": [
                    {
                        "targetId": "other",
                        "type": "page",
                        "url": "https://www.chess.com/today",
                    },
                    {
                        "targetId": "game",
                        "type": "page",
                        "url": "https://www.chess.com/game/live/123",
                    },
                ]
            }
        elif method == "Target.attachToTarget":
            result = {"sessionId": "session-1"}
        else:
            result = {"result": {"value": 42}}
        return json.dumps({"id": request["id"], "result": result})

    async def close(self):
        self.closed = True


def _patch_connect(monkeypatch, fake):
    async def fake_connect(url, **kwargs):
        return fake

    monkeypatch.setattr(cdp.websockets, "connect", fake_connect)


def test_rpc_skips_event_frames_and_returns_value(monkeypatch):
    _patch_connect(monkeypatch, FakeWs())

    async def run():
        async with cdp.Tab("ws://fake") as tab:
            return await tab.eval_js("21 * 2")

    assert asyncio.run(run()) == 42


def test_eval_js_raises_on_exception_details(monkeypatch):
    _patch_connect(monkeypatch, FakeWs(exc=True))

    async def run():
        async with cdp.Tab("ws://fake") as tab:
            await tab.eval_js("boom")

    with pytest.raises(RuntimeError, match="eval_js failed"):
        asyncio.run(run())


def test_browser_connection_attaches_to_matching_page_and_routes_session(
    monkeypatch,
):
    fake = FakeBrowserWs()
    _patch_connect(monkeypatch, fake)
    connection = cdp.BrowserConnection(
        "ws://127.0.0.1:9222/devtools/browser/token",
        r"chess\.com/game/",
    )

    async def run():
        async with cdp.Tab(connection) as tab:
            return await tab.eval_js("21 * 2")

    assert asyncio.run(run()) == 42
    assert [request["method"] for request in fake.sent] == [
        "Target.getTargets",
        "Target.attachToTarget",
        "Runtime.evaluate",
    ]
    assert "sessionId" not in fake.sent[0]
    assert "sessionId" not in fake.sent[1]
    assert fake.sent[2]["sessionId"] == "session-1"
    assert fake.closed is True
