"""Small shared helpers: disk references, document formats, request bodies."""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any, Union

from .models import Disk

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

#: Anywhere the SDK takes a disk it accepts the object, its uuid, or its slug.
DiskRef = Union[Disk, str]  # noqa: UP007 - a runtime alias, kept explicit for docs

# Formats that travel as base64 in `body_b64` rather than as text in `body`.
BINARY_FORMATS = frozenset({"pdf", "pptx", "xlsx", "xls"})
IMAGE_FORMATS = frozenset({"png", "jpg", "jpeg", "webp", "tiff", "gif", "bmp"})

_EXTENSION_FORMATS = {
    ".pdf": "pdf",
    ".pptx": "pptx",
    ".xlsx": "xlsx",
    ".xls": "xls",
    ".png": "png",
    ".jpg": "jpg",
    ".jpeg": "jpeg",
    ".webp": "webp",
    ".tif": "tiff",
    ".tiff": "tiff",
    ".gif": "gif",
    ".bmp": "bmp",
    ".docx": "docx",
    ".rtf": "rtf",
    ".odt": "odt",
    ".epub": "epub",
    ".rst": "rst",
    ".org": "org",
    ".csv": "csv",
    ".tex": "latex",
    ".html": "html",
    ".htm": "html",
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "markdown",
}


def is_uuid(value: str) -> bool:
    return bool(UUID_RE.match(str(value or "").strip()))


def disk_uuid_or_none(disk: DiskRef) -> str | None:
    """The disk's uuid when one is directly available, else ``None`` (a slug)."""
    if isinstance(disk, Disk):
        return disk.uuid or None
    value = str(disk or "").strip()
    return value if is_uuid(value) else None


def disk_slug_or_none(disk: DiskRef) -> str | None:
    """The disk's slug when one is directly available, else ``None``."""
    if isinstance(disk, Disk):
        return disk.slug or None
    value = str(disk or "").strip()
    return None if is_uuid(value) or not value else value


def format_for_path(path: str | Path) -> str:
    """The import ``format`` implied by a filename extension (``""`` when unknown)."""
    return _EXTENSION_FORMATS.get(Path(path).suffix.lower(), "")


def is_binary_format(fmt: str) -> bool:
    value = (fmt or "").strip().lower()
    return value in BINARY_FORMATS or value in IMAGE_FORMATS


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def prune(body: dict[str, Any]) -> dict[str, Any]:
    """Drop keys whose value is ``None`` so the server sees its own defaults."""
    return {key: value for key, value in body.items() if value is not None}


def flag(value: bool | None) -> str | None:
    """Render a tri-state boolean for a query string."""
    if value is None:
        return None
    return "true" if value else "false"
