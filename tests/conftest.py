"""Offline test harness.

Nothing here opens a socket. A mock transport records every request the SDK
builds and replays canned responses, so a test can assert on the exact method,
URL, query string and JSON body a method produces.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

import smartdisk
from smartdisk import SmartDisk

API = "https://smartdisk.pixilab.ai/_special/rest/Pixi/api"


class Call:
    """One recorded request."""

    def __init__(self, request: httpx.Request):
        self.method = request.method
        self.url = str(request.url)
        self.path = request.url.path
        self.params = dict(request.url.params)
        self.headers = dict(request.headers)
        raw = request.content or b""
        try:
            self.json: Any = json.loads(raw) if raw else None
        except ValueError:
            self.json = None

    @property
    def suffix(self) -> str:
        """The path with the API prefix stripped — what the docs call the route."""
        marker = "/Pixi/api"
        return self.path.split(marker, 1)[-1] if marker in self.path else self.path

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Call {self.method} {self.suffix} {self.params} {self.json}>"


class Server:
    """A scripted server. Queue responses, then read back what was asked."""

    def __init__(self) -> None:
        self.calls: list[Call] = []
        self._queue: list[httpx.Response] = []
        self._default = httpx.Response(200, json={"data": {}, "result": "success"})

    # --- scripting ---------------------------------------------------- #

    def reply(self, data: Any, *, status: int = 200, wrapped: bool = True) -> Server:
        """Queue one successful response, wrapped in the usual envelope."""
        body = {"data": data, "result": "success"} if wrapped else data
        self._queue.append(httpx.Response(status, json=body))
        return self

    def fail(self, status: int, code: str = "", **extra: Any) -> Server:
        """Queue one error response shaped the way the API shapes errors."""
        body: dict[str, Any] = {}
        if code:
            body["error"] = code
        body.update(extra)
        self._queue.append(httpx.Response(status, json=body))
        return self

    def text(self, body: str, *, status: int = 200, content_type: str = "text/csv") -> Server:
        """Queue one raw (unenveloped) body — what the export download returns."""
        self._queue.append(httpx.Response(status, text=body, headers={"content-type": content_type}))
        return self

    def raw(self, response: httpx.Response) -> Server:
        self._queue.append(response)
        return self

    # --- inspection ---------------------------------------------------- #

    @property
    def last(self) -> Call:
        assert self.calls, "no request was made"
        return self.calls[-1]

    @property
    def first(self) -> Call:
        assert self.calls, "no request was made"
        return self.calls[0]

    def __len__(self) -> int:
        return len(self.calls)

    # --- transport ------------------------------------------------------ #

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(Call(request))
        if self._queue:
            return self._queue.pop(0)
        return self._default


@pytest.fixture
def server() -> Server:
    return Server()


@pytest.fixture
def client(server: Server) -> SmartDisk:
    http = httpx.Client(transport=httpx.MockTransport(server.handler))
    sdk = SmartDisk(api_key="sd_test_key", http_client=http, max_retries=0)
    yield sdk
    sdk.close()
    http.close()


@pytest.fixture
def disk() -> smartdisk.Disk:
    """A resolved disk, so no test spends a call looking a slug up."""
    return smartdisk.Disk(uuid="11111111-2222-3333-4444-555555555555", name="Research", slug="research")


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Backoff is real code; waiting for it in tests is not."""
    monkeypatch.setattr("smartdisk._http.time.sleep", lambda _seconds: None)
