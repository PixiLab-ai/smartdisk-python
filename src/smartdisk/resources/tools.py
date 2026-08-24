"""Agent tools — the read-only endpoints for when you already know what you want.

Retrieval answers *"what do I know about this?"* by guessing well. These seven
answer *"read this source"*, *"find this exact string"*, *"rank these entities"*,
*"hand me the graph"* — so a lookup doesn't have to be phrased as a search and
hope the ranker agrees. None of them writes a row.
"""

from __future__ import annotations

from collections.abc import Mapping

from .._util import DiskRef, prune
from ..models import (
    ConsolidationRun,
    ConsolidationRuns,
    ExtractPreview,
    GrepResult,
    Hubs,
    LintReport,
    Source,
)
from ._base import Resource

__all__ = ["Tools"]

EXTRACT_TIMEOUT = 180.0


class Tools(Resource):
    """``client.tools`` — read one source, grep, export, hubs, lint, previews, audit."""

    def read(
        self, disk: DiskRef, content_uuid: str, *, offset: int | None = None, limit: int | None = None
    ) -> Source:
        """One source's actual body — the endpoint behind "open this source".

        A **document** fills ``body``, where ``total`` is its full **byte** length
        and ``offset`` a byte offset; at most 200,000 bytes come back per call, so
        page with ``offset`` while ``truncated``. A document split at its headings
        also lists its ``sections``, each readable by its own uuid.

        A **conversation** fills ``messages``, paged by position; ``limit``
        defaults to 200 and caps at 1000, and ``total`` is the full message count.

        A uuid that is not on this disk answers ``404 content_not_found`` — the
        same answer as one that does not exist, so a guess cannot confirm another
        disk's contents.

        ``GET /sd/disks/:uuid/contents/:cuuid``
        """
        url = self._disk_url(disk, f"contents/{content_uuid}")
        payload = self._t.get(url, params={"offset": offset, "limit": limit})
        return Source.from_dict(self._map(payload))

    def grep(
        self,
        disk: DiskRef,
        pattern: str,
        *,
        case_insensitive: bool | None = None,
        limit: int | None = None,
        path: str | None = None,
    ) -> GrepResult:
        """A regex over the stored text — every chat message and document body.

        The escape hatch for what semantic search is structurally bad at: an error
        code, a version string, an identifier, a rare name. It does not rank; it
        reports matches, one per matching message or document.

        The pattern is validated against RE2 — no backreferences, no lookaround —
        and is capped at 200 bytes. A pattern that does not compile comes back as
        ``400 bad_pattern`` rather than silently matching nothing.

        ``GET /sd/disks/:uuid/grep``
        """
        params = prune(
            {
                "pattern": pattern,
                "case_insensitive": "1" if case_insensitive else None,
                "limit": limit,
                "path": path,
            }
        )
        return GrepResult.from_dict(self._map(self._t.get(self._disk_url(disk, "grep"), params=params)))

    def export(
        self,
        disk: DiskRef,
        *,
        format: str | None = None,
        include: str | None = None,
        path: str | None = None,
    ) -> str:
        """The disk's **current** facts and relationships, out of the building.

        ``format`` is ``json`` (default), ``jsonld``, ``turtle`` or ``csv``;
        ``include`` defaults to ``"facts,edges"`` and accepts ``summaries`` as
        well. Only current facts are exported — superseded and retired ones are
        left behind.

        This is the one endpoint that is **not** a JSON envelope: it is a file
        download, so the rendered bytes come back as text, exactly as sent. Above
        20,000 facts in scope it refuses with
        :class:`~smartdisk.TooLargeError` rather than truncating — narrow it
        with ``path``.

        ``GET /sd/disks/:uuid/export``
        """
        params = prune({"format": format, "include": include, "path": path})
        return str(self._t.get(self._disk_url(disk, "export"), params=params, raw=True))

    def hubs(self, disk: DiskRef, *, top: int | None = None, path: str | None = None) -> Hubs:
        """Which entities are central: weighted degree and PageRank over the graph.

        Deterministic — the same graph gives the same scores, ties broken by name.
        And it refuses rather than truncates: centrality over a clipped graph is a
        wrong number, not a partial one, so above 50,000 relationships it raises
        :class:`~smartdisk.TooLargeError` and you narrow with ``path``.

        ``GET /sd/disks/:uuid/hubs``
        """
        params = prune({"top": top, "path": path})
        return Hubs.from_dict(self._map(self._t.get(self._disk_url(disk, "hubs"), params=params)))

    def lint(self, disk: DiskRef, *, path: str | None = None, limit: int | None = None) -> LintReport:
        """A read-only audit of the disk's derived memory. No model call, no writes.

        Every section is fenced independently: one that fails carries its own
        ``error`` and the report still answers 200 — so a ``200`` does not mean all
        seven succeeded. Check :attr:`LintReport.failed_sections` before trusting
        it. ``limit`` is the per-section sample cap, not a total.

        ``GET /sd/disks/:uuid/lint``
        """
        params = prune({"path": path, "limit": limit})
        return LintReport.from_dict(self._map(self._t.get(self._disk_url(disk, "lint"), params=params)))

    def extract_preview(
        self, disk: DiskRef, text: str, *, aliases: Mapping[str, str] | None = None
    ) -> ExtractPreview:
        """A dry run of fact extraction. **Stores nothing.**

        It runs the exact prompt, canonicalisation, drop filters and time gate a
        real import runs; the only thing that happens is one model call. Use it to
        see how a source will be understood before committing it, or to work out
        why a piece of text produced the facts it did.

        Over 24,000 characters the text is cut and the answer says so.

        ``POST /sd/disks/:uuid/extract-preview``
        """
        body = prune({"text": text, "aliases": dict(aliases) if aliases else None})
        url = self._disk_url(disk, "extract-preview")
        return ExtractPreview.from_dict(self._map(self._t.post(url, json=body, timeout=EXTRACT_TIMEOUT)))

    def consolidation_runs(self, disk: DiskRef, *, limit: int | None = None) -> ConsolidationRuns:
        """Consolidation history, newest first — counts only.

        Consolidation is the one part of SmartDisk that destroys text, so every
        fold is inspectable afterwards. The list deliberately never ships a diff:
        a single fold's diff includes every merged fact's full text.

        On a server without the audit trail this answers ``503 not_migrated`` —
        :class:`~smartdisk.NotAvailableError` — which means "not deployed here
        yet", not an outage.

        ``GET /sd/disks/:uuid/consolidation/runs``
        """
        payload = self._t.get(self._disk_url(disk, "consolidation/runs"), params={"limit": limit})
        return ConsolidationRuns.from_dict(self._map(payload))

    def consolidation_run(self, disk: DiskRef, run_uuid: str, *, plan: bool = False) -> ConsolidationRun:
        """One run, with the full memory diff of what it merged, closed and reworded.

        ``plan=True`` additionally returns what *undoing* that fold would do. The
        plan is computed, never executed — this is a read surface.

        ``GET /sd/disks/:uuid/consolidation/runs/:run``
        """
        url = self._disk_url(disk, f"consolidation/runs/{run_uuid}")
        payload = self._t.get(url, params={"plan": "1" if plan else None})
        return ConsolidationRun.from_dict(self._map(payload))
