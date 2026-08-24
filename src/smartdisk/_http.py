"""The HTTP layer: one place that knows about auth, retries, the response
envelope, and turning a failed status into a typed exception."""

from __future__ import annotations

import random
import time
from typing import Any

import httpx

from .errors import APIConnectionError, APITimeoutError, error_from_response

DEFAULT_BASE_URL = "https://smartdisk.pixilab.ai/_special/rest/Pixi/api"
DEFAULT_TIMEOUT = 60.0
DEFAULT_MAX_RETRIES = 2

# 500 is deliberately absent: `ingest_failed` and `chat_failed` are 500s whose
# side effects a client cannot see from the outside. 502 the docs call retryable.
RETRY_STATUSES = frozenset({429, 502, 503, 504})

MAX_BACKOFF = 10.0


def _unwrap(body: Any) -> Any:
    """Peel the ``{"data": ..., "result": "success"}`` envelope the REST API uses."""
    if isinstance(body, dict) and "data" in body and "result" in body:
        return body["data"]
    return body


def _retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("retry-after")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        return None


class Transport:
    """A configured, retrying HTTP client for one API key.

    Not part of the public surface — reach for :class:`smartdisk.SmartDisk`.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        user_agent: str = "smartdisk-python",
        http_client: httpx.Client | None = None,
    ):
        if not str(api_key or "").strip():
            raise ValueError(
                "an API key is required. Mint one on the API keys page of the web app, "
                "or set SMARTDISK_API_KEY."
            )
        self.api_key = api_key.strip()
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(timeout=timeout, follow_redirects=True)
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": user_agent,
        }

    # --- lifecycle -------------------------------------------------------- #

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Transport:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # --- urls ------------------------------------------------------------- #

    def url(self, suffix: str) -> str:
        return f"{self.base_url}/sd/{suffix.lstrip('/')}"

    def disk_url(self, disk_uuid: str, suffix: str = "") -> str:
        tail = f"/{suffix.lstrip('/')}" if suffix else ""
        return f"{self.base_url}/sd/disks/{disk_uuid}{tail}"

    # --- requests --------------------------------------------------------- #

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        timeout: float | None = None,
        raw: bool = False,
    ) -> Any:
        """Perform one request, with retries. Returns the unwrapped payload.

        ``raw=True`` returns the response text untouched — the export endpoint is
        a file download, not an envelope.
        """
        clean = {key: value for key, value in (params or {}).items() if value is not None}
        attempt = 0
        while True:
            try:
                response = self._client.request(
                    method,
                    url,
                    params=clean or None,
                    json=json,
                    headers=self._headers,
                    timeout=timeout if timeout is not None else self.timeout,
                )
            except httpx.TimeoutException as exc:
                if attempt < self.max_retries:
                    self._sleep(attempt, None)
                    attempt += 1
                    continue
                raise APITimeoutError(
                    f"the request timed out after {timeout or self.timeout:g}s [{method} {url}]", cause=exc
                ) from exc
            except httpx.HTTPError as exc:
                if attempt < self.max_retries:
                    self._sleep(attempt, None)
                    attempt += 1
                    continue
                raise APIConnectionError(
                    f"could not reach the SmartDisk server [{method} {url}]: {type(exc).__name__}", cause=exc
                ) from exc

            if response.status_code in RETRY_STATUSES and attempt < self.max_retries:
                self._sleep(attempt, _retry_after(response))
                attempt += 1
                continue

            if response.status_code >= 400:
                raise error_from_response(
                    response.status_code,
                    self._safe_json(response),
                    method=method.upper(),
                    url=url,
                    request_id=response.headers.get("x-request-id", ""),
                    text=response.text,
                )

            if raw:
                return response.text
            body = self._safe_json(response)
            if body is None:
                return response.text
            return _unwrap(body)

    # --- verbs ------------------------------------------------------------ #

    def get(self, url: str, **kwargs: Any) -> Any:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Any:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> Any:
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> Any:
        return self.request("DELETE", url, **kwargs)

    # --- internals -------------------------------------------------------- #

    @staticmethod
    def _safe_json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return None

    @staticmethod
    def _sleep(attempt: int, retry_after: float | None) -> None:
        if retry_after is not None:
            time.sleep(min(retry_after, MAX_BACKOFF))
            return
        # Exponential backoff with full jitter.
        ceiling = min(MAX_BACKOFF, 0.5 * (2**attempt))
        time.sleep(random.uniform(0.0, ceiling))
