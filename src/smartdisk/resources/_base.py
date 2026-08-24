"""Shared plumbing for the resource namespaces."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .._http import Transport
from .._util import DiskRef


class Resource:
    """One namespace on the client. Holds the transport and the disk resolver."""

    def __init__(self, transport: Transport, resolve_disk: Callable[[DiskRef], str]):
        self._t = transport
        self._resolve = resolve_disk

    def _disk_url(self, disk: DiskRef, suffix: str = "") -> str:
        return self._t.disk_url(self._resolve(disk), suffix)

    @staticmethod
    def _map(payload: Any) -> dict[str, Any]:
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _rows(payload: Any, key: str) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            source = payload
        elif isinstance(payload, dict):
            source = payload.get(key) or []
        else:
            source = []
        return [row for row in source if isinstance(row, dict)]
