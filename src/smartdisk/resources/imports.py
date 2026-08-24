"""Import — the two kinds of content that go into a disk, and the sync cursor."""

from __future__ import annotations

import time
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .._util import DiskRef, b64, disk_slug_or_none, format_for_path, is_binary_format, prune
from ..models import ChatImport, ContentList, DocumentImport, OcrResult, SyncCursor, UrlImport
from ._base import Resource

__all__ = ["Imports"]

IMPORT_TIMEOUT = 300.0

Message = Mapping[str, Any]


def _messages(messages: Iterable[Message]) -> list[dict[str, Any]]:
    """Keep only what the API takes, in the order given."""
    out: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, Mapping) or not message.get("role"):
            continue
        item: dict[str, Any] = {
            "role": str(message["role"]),
            "content": str(message.get("content") or ""),
        }
        if message.get("timestamp"):
            item["timestamp"] = str(message["timestamp"])
        if message.get("uuid"):
            item["uuid"] = str(message["uuid"])
        out.append(item)
    return out


class Imports(Resource):
    """``client.imports`` — conversations, documents, web pages, and OCR."""

    # --- conversations ---------------------------------------------------- #

    def chat(
        self,
        disk: DiskRef,
        messages: Sequence[Message],
        *,
        name: str | None = None,
        folder_path: str | None = None,
        persona: str | None = None,
        source: str | None = None,
        aliases: Mapping[str, str] | None = None,
        disk_name: str | None = None,
    ) -> ChatImport:
        """Import one conversation.

        A conversation is an **append-only thread**, not a document: re-importing
        with the same ``name`` appends to the same thread, and messages carrying a
        ``uuid`` are deduplicated individually — so re-sending an overlapping
        batch adds only what is new.

        Each message is ``{"role", "content"}`` plus, optionally, ``"timestamp"``
        (RFC 3339, its original time) and ``"uuid"`` (its id in *your* system).

        Given a **slug**, the disk is resolved or created in one call
        (``POST /sd/import/chatml``) — a script then needs only a key and a slug.
        Given a uuid or a :class:`~smartdisk.Disk`, the by-uuid route is used
        (``POST /sd/disks/:uuid/import/chatml``).
        """
        rows = _messages(messages)
        if not rows:
            raise ValueError("imports.chat: no message carried a role — nothing to import")

        slug = disk_slug_or_none(disk)
        body: dict[str, Any] = prune(
            {
                "messages": rows,
                "name": name,
                "folder_path": folder_path,
                "persona": persona,
                "source": source,
                "aliases": dict(aliases) if aliases else None,
            }
        )
        if slug:
            body["disk_slug"] = slug
            if disk_name:
                body["disk_name"] = disk_name
            url = self._t.url("import/chatml")
        else:
            url = self._disk_url(disk, "import/chatml")
        return ChatImport.from_dict(self._map(self._t.post(url, json=body, timeout=IMPORT_TIMEOUT)))

    # --- documents -------------------------------------------------------- #

    def document(
        self,
        disk: DiskRef,
        *,
        path: str | Path | None = None,
        body: str | None = None,
        body_b64: str | None = None,
        data: bytes | None = None,
        name: str | None = None,
        title: str | None = None,
        folder_path: str | None = None,
        source: str | None = None,
        format: str | None = None,
    ) -> DocumentImport:
        """Import one document.

        A document is a static unit **identified by its path** — the
        ``(folder_path, name)`` pair. Re-importing is an upsert: an unchanged body
        at the same path is skipped, a changed body replaces the old version.
        That makes a folder-sync job a matter of POSTing every file.

        Give the content exactly one way:

        * ``path=`` — read the file from disk. The format and name are inferred
          from the filename, and binary/image files are base64-encoded for you.
        * ``body=`` — text or markup (markdown, ``latex``, ``html``, ``docx``,
          ``csv``, …), converted to markdown on import.
        * ``data=`` / ``body_b64=`` — raw bytes of a binary (``pdf``, ``pptx``,
          ``xlsx``, ``xls``) or image (``png``, ``jpg``, ``webp``, ``tiff``,
          ``gif``, ``bmp``) file; images are OCR'd into structured text. A
          ``format`` is required with these.

        An AI chat-history export is auto-detected and imported as conversations
        instead — the answer then has ``is_chat_export`` set.

        ``POST /sd/disks/:uuid/import/doc``
        """
        given = [value is not None for value in (path, body, body_b64, data)]
        if sum(given) != 1:
            raise ValueError("imports.document: give exactly one of path=, body=, data=, body_b64=")

        fmt = (format or "").strip()

        if path is not None:
            file = Path(path)
            fmt = fmt or format_for_path(file)
            name = name or file.name
            if is_binary_format(fmt):
                body_b64 = b64(file.read_bytes())
            else:
                body = file.read_text(encoding="utf-8")
        elif data is not None:
            if not fmt:
                raise ValueError(
                    "imports.document: a format is required with data= "
                    "(one of pdf, pptx, xlsx, xls, png, jpg, jpeg, webp, tiff, gif, bmp)"
                )
            body_b64 = b64(data)
        elif body_b64 is not None and not fmt:
            raise ValueError("imports.document: a format is required with body_b64=")

        payload = prune(
            {
                "body": body,
                "body_b64": body_b64,
                "name": name,
                "title": title,
                "folder_path": folder_path,
                "source": source,
                "format": fmt or None,
            }
        )
        url = self._disk_url(disk, "import/doc")
        return DocumentImport.from_dict(self._map(self._t.post(url, json=payload, timeout=IMPORT_TIMEOUT)))

    def url(self, disk: DiskRef, url: str, *, name: str | None = None) -> UrlImport:
        """Import a web page, or a video's transcript.

        The fetch happens **before** the response, so a blocked, empty, dead or
        transcript-less link fails immediately and no content is created. Those
        arrive as :class:`~smartdisk.UnprocessableError` with a ``code`` of
        ``blocked``, ``no_content``, ``no_transcript`` or ``unavailable``.

        ``POST /sd/disks/:uuid/import/url``
        """
        body = prune({"url": url, "name": name})
        endpoint = self._disk_url(disk, "import/url")
        return UrlImport.from_dict(self._map(self._t.post(endpoint, json=body, timeout=IMPORT_TIMEOUT)))

    # --- utilities -------------------------------------------------------- #

    def ocr(
        self,
        *,
        path: str | Path | None = None,
        data: bytes | None = None,
        image_b64: str | None = None,
        format: str | None = None,
    ) -> OcrResult:
        """OCR one image and get its text back **without** importing anything.

        Disk-independent — this touches no disk. To actually store a scan, use
        :meth:`document` with an image ``format``.

        ``POST /sd/ocr``
        """
        given = [value is not None for value in (path, data, image_b64)]
        if sum(given) != 1:
            raise ValueError("imports.ocr: give exactly one of path=, data=, image_b64=")

        fmt = (format or "").strip()
        if path is not None:
            file = Path(path)
            fmt = fmt or format_for_path(file)
            image_b64 = b64(file.read_bytes())
        elif data is not None:
            image_b64 = b64(data)

        body = prune({"image_b64": image_b64, "format": fmt or None})
        payload = self._t.post(self._t.url("ocr"), json=body, timeout=IMPORT_TIMEOUT)
        return OcrResult.from_dict(self._map(payload))

    def last(self, disk: DiskRef) -> SyncCursor:
        """Where the last incremental import left off.

        ``empty`` means nothing has been imported yet. Otherwise send only the
        messages strictly newer than ``(original_timestamp, original_uuid)``. The
        cursor lives with the disk, not the client, so it stays correct even if
        the disk is rebuilt.

        ``GET /sd/disks/:uuid/import/last``
        """
        return SyncCursor.from_dict(self._map(self._t.get(self._disk_url(disk, "import/last"))))

    def retry(self, disk: DiskRef, content_uuid: str) -> str:
        """Re-queue a source whose processing failed. Returns its new status.

        ``POST /sd/disks/:uuid/contents/:cuuid/retry``
        """
        url = self._disk_url(disk, f"contents/{content_uuid}/retry")
        return str(self._map(self._t.post(url, json={})).get("status", ""))

    def wait_until_processed(
        self,
        disk: DiskRef,
        *,
        timeout: float = 1800.0,
        poll_interval: float = 5.0,
        wait_for_consolidation: bool = False,
        on_progress: Any = None,
    ) -> ContentList:
        """Block until every source on the disk reaches ``processed``.

        Import is asynchronous — content moves ``queued -> processing ->
        processed`` — so anything that reads memory right after an import reads
        an empty disk. This polls ``GET /sd/disks/:uuid/contents`` until it is
        done.

        Set ``wait_for_consolidation`` to also wait out the disk-level fact
        dedup/supersession pass; that is what a benchmark wants and what an
        interactive script usually does not (it is serialised server-side and can
        sit behind other work).

        ``on_progress`` is called with the status line whenever it changes.

        Raises :class:`RuntimeError` if a source ends ``failed``, and
        :class:`TimeoutError` if the deadline passes.
        """
        started = time.monotonic()
        previous = ""
        while True:
            listing = ContentList.from_dict(self._map(self._t.get(self._disk_url(disk, "contents"))))
            failed = listing.failed
            if failed:
                names = ", ".join(row.name or row.uuid for row in failed[:5])
                raise RuntimeError(f"{len(failed)} source(s) failed to process: {names}")

            done = sum(1 for row in listing.contents if row.is_processed)
            line = f"{done}/{len(listing.contents)} processed"
            if listing.consolidating:
                line += ", consolidating"
            if on_progress is not None and line != previous:
                on_progress(line)
                previous = line

            settled = listing.all_processed and (not wait_for_consolidation or not listing.consolidating)
            if settled:
                return listing
            if time.monotonic() - started > timeout:
                raise TimeoutError(f"still {line} after {timeout:g}s")
            time.sleep(poll_interval)
