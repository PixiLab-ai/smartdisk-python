"""Typed exceptions, one per failure the API documents.

Every error the server returns carries an ``error`` code and sometimes a
``detail``. The SDK maps the code first and the HTTP status second, so
``except AccessRequiredError`` catches the one condition retrying will never fix,
while ``except SmartDiskError`` still catches everything.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = [
    "SmartDiskError",
    "APIConnectionError",
    "APITimeoutError",
    "APIStatusError",
    "BadRequestError",
    "AuthenticationError",
    "ForbiddenError",
    "AccessRequiredError",
    "SessionRequiredError",
    "NotFoundError",
    "TooLargeError",
    "UnprocessableError",
    "RateLimitError",
    "ServerError",
    "UpstreamError",
    "NotAvailableError",
    "error_from_response",
]


class SmartDiskError(Exception):
    """Base class for everything this SDK raises."""


class APIConnectionError(SmartDiskError):
    """The server could not be reached."""

    def __init__(
        self,
        message: str = "could not reach the SmartDisk server",
        *,
        cause: Exception | None = None,
    ):
        super().__init__(message)
        self.__cause__ = cause


class APITimeoutError(APIConnectionError):
    """The request timed out before the server answered."""


class APIStatusError(SmartDiskError):
    """The server answered with a 4xx or 5xx.

    Attributes:
        status: The HTTP status code.
        code: The ``error`` code from the body (``""`` when the body had none).
        detail: The ``detail`` string from the body (``""`` when absent).
        body: The parsed body, for the fields a specific error carries
            (``facts_total``/``max_facts`` on ``too_large``, and so on).
        request_id: The server's request id, when it sent one.
    """

    status: int = 0

    def __init__(
        self,
        message: str,
        *,
        status: int,
        code: str = "",
        detail: str = "",
        body: Any = None,
        request_id: str = "",
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.detail = detail
        self.body = body if body is not None else {}
        self.request_id = request_id


class BadRequestError(APIStatusError):
    """400 — malformed request, bad JSON, or a missing required field."""


class AuthenticationError(APIStatusError):
    """401 — the key is missing, malformed, or revoked."""


class ForbiddenError(APIStatusError):
    """403 — authenticated, but not allowed to touch this."""


class AccessRequiredError(ForbiddenError):
    """403 ``smartdisk_access_required`` — the account has no SmartDisk access.

    Retrying will not fix this; an administrator has to enable the account.
    """


class SessionRequiredError(ForbiddenError):
    """403 ``session_required`` — the route needs a browser session, not an API key.

    Key management is the only such surface, and it is deliberately outside this SDK.
    """


class NotFoundError(APIStatusError):
    """404 — no such disk, source, or run *on this disk*."""


class TooLargeError(APIStatusError):
    """413 — the request covers more memory than the endpoint will answer for.

    Narrow it with a folder ``path``. The limits are on the exception:
    ``facts_total``/``max_facts`` for an export, ``edges_total``/``max_edges``
    for a centrality query.
    """

    @property
    def facts_total(self) -> int | None:
        return _int_or_none(self.body.get("facts_total"))

    @property
    def max_facts(self) -> int | None:
        return _int_or_none(self.body.get("max_facts"))

    @property
    def edges_total(self) -> int | None:
        return _int_or_none(self.body.get("edges_total"))

    @property
    def max_edges(self) -> int | None:
        return _int_or_none(self.body.get("max_edges"))


class UnprocessableError(APIStatusError):
    """422 — valid request, but it could not be fulfilled.

    A URL import that was ``blocked``, returned ``no_content``, had
    ``no_transcript``, or was ``unavailable``.
    """


class RateLimitError(APIStatusError):
    """429 — too many requests. Retried automatically before it reaches you."""


class ServerError(APIStatusError):
    """500 — the server failed. ``ingest_failed`` and ``chat_failed`` live here."""


class UpstreamError(APIStatusError):
    """502 — a service the request depends on failed (OCR, extraction). Retryable."""


class NotAvailableError(APIStatusError):
    """503 — the feature is not deployed on this server yet. Not an outage."""


# Codes whose meaning is sharper than their status.
_BY_CODE: dict[str, type[APIStatusError]] = {
    "smartdisk_access_required": AccessRequiredError,
    "session_required": SessionRequiredError,
    "not_migrated": NotAvailableError,
}

_BY_STATUS: dict[int, type[APIStatusError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    403: ForbiddenError,
    404: NotFoundError,
    413: TooLargeError,
    422: UnprocessableError,
    429: RateLimitError,
    500: ServerError,
    502: UpstreamError,
    503: NotAvailableError,
}

# Read to a human when the body carried a code but no detail.
_MESSAGES: dict[str, str] = {
    "invalid_api_key": "the API key is missing, malformed, or revoked",
    "unauthorized": "no credentials reached the server",
    "smartdisk_access_required": "this account has not been granted SmartDisk access",
    "session_required": "this route needs a signed-in browser session, not an API key",
    "forbidden": "this disk does not belong to the account the key acts as",
    "disk_not_found": "no disk with that id",
    "content_not_found": "no such source on this disk",
    "run_not_found": "no such consolidation run on this disk",
    "not_migrated": "this feature is not deployed on the server yet",
    "too_large": "the request covers more memory than this endpoint will answer for",
}


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def error_from_response(
    status: int,
    body: Any,
    *,
    method: str = "",
    url: str = "",
    request_id: str = "",
    text: str = "",
) -> APIStatusError:
    """Build the right exception for one failed response."""
    payload: dict[str, Any] = body if isinstance(body, dict) else {}
    # An error may sit inside the {"data": ...} envelope.
    inner = payload.get("data")
    if isinstance(inner, dict) and ("error" in inner or "detail" in inner):
        payload = inner

    code = str(payload.get("error") or "").strip()
    if not code:
        # Some deployments carry the machine code in "message" instead of "error".
        candidate = str(payload.get("message") or "").strip()
        if re.fullmatch(r"[a-z0-9_.-]{2,64}", candidate):
            code = candidate
    detail = str(payload.get("detail") or "").strip()

    cls = _BY_CODE.get(code) or _BY_STATUS.get(status)
    if cls is None:
        cls = APIStatusError if status < 500 else ServerError

    described = _MESSAGES.get(code) or code or (text or "").strip().replace("\n", " ")[:200]
    where = f" [{method} {url}]" if method and url else ""
    message = f"HTTP {status}{where}"
    if described:
        message = f"{message}: {described}"
    if detail:
        message = f"{message} — {detail}"

    return cls(message, status=status, code=code, detail=detail, body=payload, request_id=request_id)
