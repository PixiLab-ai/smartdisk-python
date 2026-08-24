"""Memory — what processing produced, how it is organised, and the write verbs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .._util import DiskRef, prune
from ..models import (
    Answer,
    ContentList,
    Ecosystem,
    FactGroups,
    Folder,
    GraphResult,
    ProfileView,
    SubjectGraph,
    Tag,
)
from ..models import (
    Memory as MemoryView,
)
from ._base import Resource

__all__ = ["Memory"]

ASK_TIMEOUT = 180.0


class Memory(Resource):
    """``client.memory`` — read what the disk knows, and write to it directly."""

    # --- grounded answer -------------------------------------------------- #

    def ask(
        self,
        disk: DiskRef,
        query: str,
        *,
        path: str | None = None,
        model: str | None = None,
        language: str | None = None,
        history: Sequence[Mapping[str, str]] | None = None,
        categories: Sequence[str] | None = None,
        tags: Sequence[str] | None = None,
        since: str | None = None,
        until: str | None = None,
        graph_expand: bool | None = None,
        graph_hops: int | None = None,
        expand: bool | None = None,
        expand_max: int | None = None,
        fictional: bool | None = None,
    ) -> Answer:
        """Ask the disk a question and get one grounded, cited answer.

        The one-call alternative to retrieve-then-prompt: the server retrieves,
        spends **one** model call, and returns the answer with the same citations
        :meth:`~smartdisk.SmartDisk.retrieve` would have given you. Use
        ``retrieve`` instead when your own model will reason over the passages.

        ``model`` picks the answer tier — ``"fast"`` for cheap lookups,
        ``"main"`` (the default) otherwise. ``history`` carries prior turns as
        ``{"role", "content"}`` for follow-up questions.

        ``POST /sd/disks/:uuid/chat``
        """
        body = prune(
            {
                "query": query,
                "path": path,
                "model": model,
                "language": language,
                "history": [dict(turn) for turn in history] if history else None,
                "categories": list(categories) if categories else None,
                "tags": list(tags) if tags else None,
                "since": since,
                "until": until,
                "graph_expand": graph_expand,
                "graph_hops": graph_hops,
                "expand": expand,
                "expand_max": expand_max,
                "fictional": fictional,
            }
        )
        payload = self._t.post(self._disk_url(disk, "chat"), json=body, timeout=ASK_TIMEOUT)
        return Answer.from_dict(self._map(payload))

    # --- reading ---------------------------------------------------------- #

    def contents(self, disk: DiskRef) -> ContentList:
        """Every stored source with its pipeline status.

        The ``*_done`` flags say a stage *ran*; ``freshness`` and ``stale`` say
        whether it ran over everything that is there now. A busy thread sitting
        ``stale`` between summary windows is a normal state, not a fault.

        ``GET /sd/disks/:uuid/contents``
        """
        return ContentList.from_dict(self._map(self._t.get(self._disk_url(disk, "contents"))))

    def facts(self, disk: DiskRef) -> MemoryView:
        """The derived-memory view: enduring facts, the latest summary, the tags.

        Facts come back central-first — ``origin="chat"`` facts are enduring
        truths, ``origin="doc"`` facts are local to the document they came from.
        ``.facts`` is usually what you want; ``.summary`` and ``.tags`` ride along.

        ``GET /sd/disks/:uuid/memory``
        """
        return MemoryView.from_dict(self._map(self._t.get(self._disk_url(disk, "memory"))))

    def groups(self, disk: DiskRef) -> FactGroups:
        """Facts grouped by ``(subject, predicate)`` — and what they replaced.

        Nothing is ever deleted, so a group is a small history. Each history entry
        carries ``close_kind``: ``superseded`` (the world changed), ``replaced``
        (same truth, better wording), ``retired`` (closed with no successor) or
        ``expired``.

        ``GET /sd/disks/:uuid/groups``
        """
        return FactGroups.from_dict(self._map(self._t.get(self._disk_url(disk, "groups"))))

    def subjects(self, disk: DiskRef, *, limit: int | None = None) -> SubjectGraph:
        """The knowledge graph as nodes and edges. ``limit=0`` returns all subjects.

        The response reports its own truncation, so render "showing 300 of 1,284"
        rather than presenting a slice as the whole graph.

        ``GET /sd/disks/:uuid/subjects``
        """
        payload = self._t.get(self._disk_url(disk, "subjects"), params={"limit": limit})
        return SubjectGraph.from_dict(self._map(payload))

    def tags(self, disk: DiskRef, *, path: str | None = None) -> list[Tag]:
        """The disk's tag vocabulary with usage counts, most-used first.

        This is what the ``tags`` retrieval filter can match. Scope it with
        ``path`` so a folder-scoped surface only offers tags that occur there.

        ``GET /sd/disks/:uuid/tags``
        """
        payload = self._t.get(self._disk_url(disk, "tags"), params={"path": path})
        return [Tag.from_dict(row) for row in self._rows(payload, "tags")]

    def profile(self, disk: DiskRef) -> ProfileView:
        """The disk's standing profile and its memory index.

        Where the profile says *who this disk is about*, the index says *what
        exists in it*. Either half can be present without the other, and both are
        ``None`` on a young disk. Both also ride every retrieval response as
        ``stable``, so you rarely need this call in a hot path.

        ``GET /sd/disks/:uuid/profile``
        """
        return ProfileView.from_dict(self._map(self._t.get(self._disk_url(disk, "profile"))))

    def regenerate_profile(self, disk: DiskRef) -> ProfileView:
        """Force a fresh profile synthesis now — one model call, a few seconds.

        ``POST /sd/disks/:uuid/profile/regen``
        """
        payload = self._t.post(self._disk_url(disk, "profile/regen"), json={}, timeout=ASK_TIMEOUT)
        return ProfileView.from_dict(self._map(payload))

    def ecosystem(self, disk: DiskRef, *, limit: int | None = None) -> Ecosystem:
        """The association graph — sources, tags, facts and the links between them.

        Pruned server-side so it stays renderable on a large disk; ``limit=0``
        lifts the fact cap. The cap is reported, not hidden.

        ``GET /sd/disks/:uuid/ecosystem``
        """
        payload = self._t.get(self._disk_url(disk, "ecosystem"), params={"limit": limit})
        return Ecosystem.from_dict(self._map(payload))

    def graph(self, disk: DiskRef, q: str, *, depth: int | None = None) -> GraphResult:
        """A targeted structural question about the graph. No embeddings, no fuzziness.

        Three shapes, auto-detected from ``q``: ``"alex..northwind"`` is the
        shortest path between two entities, a bare ``"alex"`` is its neighbours,
        and ``"alex:works_at:"`` is an edge filter where any empty part is a
        wildcard. Use retrieval for "what do I know about X"; use this for "how
        does X relate to Y".

        ``depth`` (1-6, default 4) caps the path/neighbour traversal.

        ``GET /sd/disks/:uuid/graph-query``
        """
        payload = self._t.get(self._disk_url(disk, "graph-query"), params={"q": q, "depth": depth})
        return GraphResult.from_dict(self._map(payload))

    # --- organising ------------------------------------------------------- #

    def delete_content(self, disk: DiskRef, content_uuid: str) -> int:
        """Remove one source. Returns how many chunks went with it.

        Disk-wide facts and summaries are kept by design — they are derived across
        the whole disk, not tied to one source.

        ``DELETE /sd/disks/:uuid/contents/:cuuid``
        """
        payload = self._map(self._t.delete(self._disk_url(disk, f"contents/{content_uuid}")))
        return int(payload.get("chunks_removed") or 0)

    def move_content(self, disk: DiskRef, content_uuid: str, folder_path: str) -> bool:
        """Move one source into another folder.

        ``POST /sd/disks/:uuid/contents/:cuuid/move``
        """
        url = self._disk_url(disk, f"contents/{content_uuid}/move")
        payload = self._map(self._t.post(url, json={"folder_path": folder_path}))
        return bool(payload.get("moved", True))

    def folders(self, disk: DiskRef) -> list[Folder]:
        """The disk's virtual folders with their content counts.

        ``GET /sd/disks/:uuid/folders``
        """
        payload = self._t.get(self._disk_url(disk, "folders"))
        return [Folder.from_dict(row) for row in self._rows(payload, "folders")]

    def create_folder(self, disk: DiskRef, path: str) -> dict[str, Any]:
        """Create a folder. Ancestors are created with it.

        ``POST /sd/disks/:uuid/folders``
        """
        return self._map(self._t.post(self._disk_url(disk, "folders"), json={"path": path}))

    def delete_folder(self, disk: DiskRef, path: str) -> dict[str, Any]:
        """Delete an empty folder. Refused while it still holds content.

        ``DELETE /sd/disks/:uuid/folders?path=``
        """
        return self._map(self._t.delete(self._disk_url(disk, "folders"), params={"path": path}))

    # --- identity aliases ------------------------------------------------- #

    def aliases(self, disk: DiskRef) -> dict[str, str]:
        """The disk-level ``{variant: canonical}`` alias map.

        ``GET /sd/disks/:uuid/aliases``
        """
        payload = self._map(self._t.get(self._disk_url(disk, "aliases")))
        return {str(k): str(v) for k, v in self._map(payload.get("aliases")).items()}

    def set_aliases(self, disk: DiskRef, aliases: Mapping[str, str]) -> dict[str, str]:
        """Set the disk-level alias map so one subject's facts land together.

        Changes take effect on the **next** derive of a source; reprocess a source
        to apply them to memory already extracted. An empty map clears it.

        ``PUT /sd/disks/:uuid/aliases``
        """
        payload = self._map(self._t.put(self._disk_url(disk, "aliases"), json={"aliases": dict(aliases)}))
        return {str(k): str(v) for k, v in self._map(payload.get("aliases")).items()}

    def content_aliases(self, disk: DiskRef, content_uuid: str) -> dict[str, str]:
        """One conversation's alias map — e.g. its two roles mapped to real names.

        ``GET /sd/disks/:uuid/contents/:cuuid/aliases``
        """
        payload = self._map(self._t.get(self._disk_url(disk, f"contents/{content_uuid}/aliases")))
        return {str(k): str(v) for k, v in self._map(payload.get("aliases")).items()}

    def set_content_aliases(
        self, disk: DiskRef, content_uuid: str, aliases: Mapping[str, str]
    ) -> dict[str, str]:
        """Set one conversation's alias map. Content-level overrides disk-level.

        ``PUT /sd/disks/:uuid/contents/:cuuid/aliases``
        """
        url = self._disk_url(disk, f"contents/{content_uuid}/aliases")
        payload = self._map(self._t.put(url, json={"aliases": dict(aliases)}))
        return {str(k): str(v) for k, v in self._map(payload.get("aliases")).items()}

    # --- writing ---------------------------------------------------------- #

    def remember(
        self,
        disk: DiskRef,
        text: str,
        *,
        subject: str | None = None,
        predicate: str | None = None,
        object: str | None = None,
        category: str | None = None,
        priority: int | None = None,
        fictional: bool | None = None,
    ) -> str:
        """Assert one fact directly, bypassing extraction. Returns its uuid.

        The deliberate "keep this" verb. Supplying the ``subject`` /
        ``predicate`` / ``object`` triple is optional but strongly recommended: it
        is what groups the fact with the other statements about the same relation
        and puts it on the knowledge graph.

        ``POST /sd/disks/:uuid/remember``
        """
        body = prune(
            {
                "text": text,
                "subject": subject,
                "predicate": predicate,
                "object": object,
                "category": category,
                "priority": priority,
                "fictional": fictional,
            }
        )
        payload = self._map(self._t.post(self._disk_url(disk, "remember"), json=body))
        return str(payload.get("fact_uuid") or "")

    def forget(self, disk: DiskRef, fact_uuid: str) -> int:
        """Retire a fact so it stops being recalled. Returns how many were closed.

        A bitemporal close, not a hard delete: the fact leaves the current layer
        and stays in the history as something that was once true. ``0`` means it
        was already retired.

        ``POST /sd/disks/:uuid/forget``
        """
        payload = self._map(self._t.post(self._disk_url(disk, "forget"), json={"fact_uuid": fact_uuid}))
        return int(payload.get("closed") or 0)

    def feedback(self, disk: DiskRef, fact_uuids: Sequence[str], score: float) -> int:
        """Record whether retrieved facts actually helped. Returns how many were updated.

        The learning half of retrieval: a positive score makes the named facts
        easier to recall later, a negative one makes them harder. Nothing is
        deleted. The uuids are the ``object_uuid`` values from citations.

        ``POST /sd/disks/:uuid/feedback``
        """
        clean = [str(value).strip() for value in fact_uuids if str(value).strip()]
        if not clean:
            raise ValueError("memory.feedback: at least one fact uuid is required")
        body = {"fact_uuids": clean, "score": score}
        payload = self._map(self._t.post(self._disk_url(disk, "feedback"), json=body))
        return int(payload.get("updated") or 0)

    def reprioritize(self, disk: DiskRef, fact_uuid: str, priority: int) -> int:
        """Raise or lower how important one fact is considered, from 1 to 100.

        A direct override on the fact's standing. The fact itself is unchanged.

        ``POST /sd/disks/:uuid/reprioritize``
        """
        if not 1 <= int(priority) <= 100:
            raise ValueError("memory.reprioritize: priority must be between 1 and 100")
        body = {"fact_uuid": fact_uuid, "priority": int(priority)}
        payload = self._map(self._t.post(self._disk_url(disk, "reprioritize"), json=body))
        return int(payload.get("updated") or 0)
