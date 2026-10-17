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
