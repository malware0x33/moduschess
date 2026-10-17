import io
import json

from chessbot.cdp import find_tab


def _fake_urlopen(payload):
    class R:
        def read(self):
            return json.dumps(payload).encode()

    return R()


def test_find_tab_matches_page_url(monkeypatch):
    import chessbot.cdp as cdp

    tabs = [
        {"type": "page", "url": "https://www.chess.com/today", "webSocketDebuggerUrl": "ws://x/1"},
        {"type": "page", "url": "https://www.chess.com/game/live/123", "webSocketDebuggerUrl": "ws://x/2"},
        {"type": "iframe", "url": "https://www.chess.com/game/live/999", "webSocketDebuggerUrl": "ws://x/3"},
    ]
    monkeypatch.setattr(cdp.urllib.request, "urlopen", lambda url: _fake_urlopen(tabs))
    assert cdp.find_tab("http://127.0.0.1:9222", r"chess\.com/game/") == "ws://x/2"


def test_find_tab_no_match_returns_none(monkeypatch):
    import chessbot.cdp as cdp

    monkeypatch.setattr(cdp.urllib.request, "urlopen", lambda url: _fake_urlopen([]))
    assert cdp.find_tab("http://127.0.0.1:9222", r"chess\.com") is None
