"""Typed results.

Plain dataclasses, built by ``from_dict`` classmethods that ignore keys they
don't know and keep the whole decoded payload on ``.raw``. A server that grows a
field cannot break a pinned client, and nothing is lost — the new field is on
``.raw`` the day it ships.

Parsing is deliberately forgiving: a null where a number was expected yields the
default rather than a traceback. The one thing never coerced is ``content_hash``,
a 64-bit integer the server sends as a string precisely so it survives JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "Disk",
    "DiskSettings",
    "Whoami",
    "ChatImport",
    "DocumentImport",
    "UrlImport",
    "OcrResult",
    "SyncCursor",
    "Explain",
    "Citation",
    "StableBlock",
    "Ledger",
    "Retrieval",
    "Answer",
    "Freshness",
    "Content",
    "ContentList",
    "Tag",
    "Fact",
    "Memory",
    "FactGroup",
    "FactGroups",
    "Subject",
    "Edge",
    "SubjectGraph",
    "GraphResult",
    "Profile",
    "MemoryIndex",
    "ProfileView",
    "Folder",
    "Ecosystem",
    "Message",
    "Section",
    "Source",
    "GrepHit",
    "GrepResult",
    "Hub",
    "Hubs",
    "LintSection",
    "LintReport",
    "ExtractedFact",
    "ExtractPreview",
    "ConsolidationRun",
    "ConsolidationRuns",
]


# --------------------------------------------------------------------------- #
# coercion helpers — forgiving on purpose
# --------------------------------------------------------------------------- #


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _s(data: dict, key: str, default: str = "") -> str:
    value = data.get(key)
    return default if value is None else str(value)


def _opt_s(data: dict, key: str) -> str | None:
    value = data.get(key)
    if value is None or value == "":
        return None
    return str(value)


def _i(data: dict, key: str, default: int = 0) -> int:
    try:
        return int(data.get(key))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _opt_i(data: dict, key: str) -> int | None:
    if data.get(key) is None:
        return None
    return _i(data, key)


def _f(data: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(data.get(key))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _b(data: dict, key: str, default: bool = False) -> bool:
    value = data.get(key)
    return default if value is None else bool(value)


def _strs(data: dict, key: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


# --------------------------------------------------------------------------- #
# disks
# --------------------------------------------------------------------------- #


@dataclass
class Disk:
    """One body of memory."""

    uuid: str
    name: str = ""
    slug: str = ""
    description: str = ""
    document_count: int | None = None
    tokens_stored: int | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Disk:
        return cls(
            uuid=_s(data, "uuid"),
            name=_s(data, "name"),
            slug=_s(data, "slug"),
            description=_s(data, "description"),
            document_count=_opt_i(data, "document_count"),
            tokens_stored=_opt_i(data, "tokens_stored"),
            raw=data,
        )


@dataclass
class DiskSettings:
    """The disk's ``about`` note and whether background processing is paused."""

    about: str = ""
    paused: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DiskSettings:
        return cls(about=_s(data, "about"), paused=_b(data, "paused"), raw=data)


@dataclass
class Whoami:
    """Which server the key is talking to."""

    env: str = ""
    hostname: str = ""
    bearer: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Whoami:
        return cls(env=_s(data, "env"), hostname=_s(data, "hostname"), bearer=_b(data, "bearer"), raw=data)


# --------------------------------------------------------------------------- #
# imports
# --------------------------------------------------------------------------- #


@dataclass
class ChatImport:
    """The result of importing one conversation."""

    disk_uuid: str = ""
    content_uuid: str = ""
    messages_added: int = 0
    skipped: bool = False
    status: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChatImport:
        return cls(
            disk_uuid=_s(data, "disk_uuid"),
            content_uuid=_s(data, "content_uuid"),
            messages_added=_i(data, "messages_added"),
            skipped=_b(data, "skipped"),
            status=_s(data, "status"),
            raw=data,
        )


@dataclass
class DocumentImport:
    """The result of importing one document.

    An AI chat-history export is recognised on the way in and imported as
    conversations instead; that answer sets ``mode`` to ``"chat-export"`` and
    fills ``conversations`` / ``messages`` instead of ``content_uuid``.
    """

    content_uuid: str = ""
    skipped: bool = False
    status: str = ""
    mode: str = ""
    format: str = ""
    conversations: int = 0
    messages: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_chat_export(self) -> bool:
        return self.mode == "chat-export"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentImport:
        return cls(
            content_uuid=_s(data, "content_uuid"),
            skipped=_b(data, "skipped"),
            status=_s(data, "status"),
            mode=_s(data, "mode"),
            format=_s(data, "format"),
            conversations=_i(data, "conversations"),
            messages=_i(data, "messages"),
            raw=data,
        )


@dataclass
class UrlImport:
    """The result of importing a web page or a video transcript."""

    content_uuid: str = ""
    skipped: bool = False
    status: str = ""
    source_type: str = ""
    title: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UrlImport:
        return cls(
            content_uuid=_s(data, "content_uuid"),
            skipped=_b(data, "skipped"),
            status=_s(data, "status"),
            source_type=_s(data, "source_type"),
            title=_s(data, "title"),
            raw=data,
        )


@dataclass
class OcrResult:
    """Text pulled out of one image, without importing it."""

    text: str = ""
    chars: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OcrResult:
        return cls(text=_s(data, "text"), chars=_i(data, "chars"), raw=data)


@dataclass
class SyncCursor:
    """Where an incremental import left off.

    ``empty`` means nothing has been imported yet — start from the beginning.
    Otherwise send only the messages strictly newer than
    ``(original_timestamp, original_uuid)``.
    """

    content_uuid: str = ""
    original_uuid: str = ""
    original_timestamp: str = ""
    name: str = ""
    empty: bool = True
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SyncCursor:
        return cls(
            content_uuid=_s(data, "content_uuid"),
            original_uuid=_s(data, "original_uuid"),
            original_timestamp=_s(data, "original_timestamp"),
            name=_s(data, "name"),
            empty=_b(data, "empty", True),
            raw=data,
        )


# --------------------------------------------------------------------------- #
# retrieval
# --------------------------------------------------------------------------- #


@dataclass
class Explain:
    """Why one passage ranked where it did. Diagnostic only."""

    lanes: list[str] = field(default_factory=list)
    lane_ranks: dict[str, int] = field(default_factory=dict)
    rrf: float = 0.0
    rerank: float = 0.0
    priors: dict[str, Any] = field(default_factory=dict)
    final_rank: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Explain:
        ranks = _dict(data.get("lane_ranks"))
        return cls(
            lanes=_strs(data, "lanes"),
            lane_ranks={str(k): int(v) for k, v in ranks.items() if isinstance(v, int)},
            rrf=_f(data, "rrf"),
            rerank=_f(data, "rerank"),
            priors=_dict(data.get("priors")),
            final_rank=_i(data, "final_rank"),
            raw=data,
        )


@dataclass
class Citation:
    """The source passage behind one ``[n]`` in a retrieved block."""

    n: int = 0
    type: str = ""
    content_uuid: str = ""
    content_name: str = ""
    heading_path: str = ""
    snippet: str = ""
    score: float = 0.0
    object_uuid: str = ""
    explain: Explain | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Citation:
        trace = data.get("explain")
        return cls(
            n=_i(data, "n"),
            type=_s(data, "type"),
            content_uuid=_s(data, "content_uuid"),
            content_name=_s(data, "content_name"),
            heading_path=_s(data, "heading_path"),
            snippet=_s(data, "snippet"),
            score=_f(data, "score"),
            object_uuid=_s(data, "object_uuid"),
            explain=Explain.from_dict(trace) if isinstance(trace, dict) else None,
            raw=data,
        )


@dataclass
class StableBlock:
    """The disk's standing profile + memory index, as one prompt block.

    Identical across calls until ``hash`` changes — pin it at the end of your
    system prompt and re-inject only on a new hash.
    """

    block: str = ""
    hash: str = ""
    tokens: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StableBlock:
        return cls(block=_s(data, "block"), hash=_s(data, "hash"), tokens=_i(data, "tokens"), raw=data)


@dataclass
class Ledger:
    """Present only when the cross-turn recall ledger engaged."""

    session_id: str = ""
    dedup_turns: int = 0
    excluded: int = 0
    recorded: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Ledger:
        return cls(
            session_id=_s(data, "session_id"),
            dedup_turns=_i(data, "dedup_turns"),
            excluded=_i(data, "excluded"),
            recorded=_i(data, "recorded"),
            raw=data,
        )


@dataclass
class Retrieval:
    """Ready-to-prompt context. No model was in the loop."""

    block: str = ""
    citations: list[Citation] = field(default_factory=list)
    tokens_used: int = 0
    drilled: bool = False
    expanded: bool = False
    stable: StableBlock | None = None
    ledger: Ledger | None = None
    retrieve_ms: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def __bool__(self) -> bool:
        """False when retrieval found nothing above the relevance floor."""
        return bool(self.block or self.citations)

    @property
    def object_uuids(self) -> list[str]:
        """Every cited memory object, in rank order — feed back as ``exclude``."""
        seen: list[str] = []
        for citation in self.citations:
            if citation.object_uuid and citation.object_uuid not in seen:
                seen.append(citation.object_uuid)
        return seen

    @property
    def content_uuids(self) -> list[str]:
        """Distinct source uuids in rank order (first citation wins)."""
        seen: list[str] = []
        for citation in self.citations:
            if citation.content_uuid and citation.content_uuid not in seen:
                seen.append(citation.content_uuid)
        return seen

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Retrieval:
        stable = data.get("stable")
        ledger = data.get("ledger")
        return cls(
            block=_s(data, "block"),
            citations=[Citation.from_dict(row) for row in _rows(data.get("citations"))],
            tokens_used=_i(data, "tokens_used"),
            drilled=_b(data, "drilled"),
            expanded=_b(data, "expanded"),
            stable=StableBlock.from_dict(stable) if isinstance(stable, dict) else None,
            ledger=Ledger.from_dict(ledger) if isinstance(ledger, dict) else None,
            retrieve_ms=_f(data, "retrieve_ms"),
            raw=data,
        )


@dataclass
class Answer:
    """A grounded answer written by the server from what it retrieved."""

    answer: str = ""
    citations: list[Citation] = field(default_factory=list)
    drilled: bool = False
    tokens_used: int = 0
    retrieve_ms: float = 0.0
    answer_ms: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def __str__(self) -> str:
        return self.answer

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Answer:
        return cls(
            answer=_s(data, "answer"),
            citations=[Citation.from_dict(row) for row in _rows(data.get("citations"))],
            drilled=_b(data, "drilled"),
            tokens_used=_i(data, "tokens_used"),
            retrieve_ms=_f(data, "retrieve_ms"),
            answer_ms=_f(data, "answer_ms"),
            raw=data,
        )


# --------------------------------------------------------------------------- #
# contents
# --------------------------------------------------------------------------- #


@dataclass
class Freshness:
    """What the latest summary of one source actually covered."""

    source_count: int = 0
    window_count: int = 0
    generated_at: str = ""
    pending: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Freshness:
        return cls(
            source_count=_i(data, "source_count"),
            window_count=_i(data, "window_count"),
            generated_at=_s(data, "generated_at"),
            pending=_b(data, "pending"),
            raw=data,
        )


@dataclass
class Content:
    """One imported source, with its pipeline status."""

    uuid: str = ""
    name: str = ""
    folder_path: str = ""
    content_type: str = ""
    status: str = ""
    chunking_done: bool = False
    facts_done: bool = False
    summary_done: bool = False
    tags_done: bool = False
    created_at: str = ""
    message_count: int = 0
    preview: str = ""
    tags: list[str] = field(default_factory=list)
    source: str = ""
    content_hash: str = ""
    freshness: Freshness | None = None
    stale: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_chat(self) -> bool:
        return self.content_type == "chat"

    @property
    def is_processed(self) -> bool:
        return self.status == "processed"

    @property
    def is_failed(self) -> bool:
        return self.status == "failed"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Content:
        fresh = data.get("freshness")
        return cls(
            uuid=_s(data, "uuid"),
            name=_s(data, "name"),
            folder_path=_s(data, "folder_path"),
            content_type=_s(data, "content_type"),
            status=_s(data, "status"),
            chunking_done=_b(data, "chunking_done"),
            facts_done=_b(data, "facts_done"),
            summary_done=_b(data, "summary_done"),
            tags_done=_b(data, "tags_done"),
            created_at=_s(data, "created_at"),
            message_count=_i(data, "message_count"),
            preview=_s(data, "preview"),
            tags=_strs(data, "tags"),
            source=_s(data, "source"),
            content_hash=_s(data, "content_hash"),
            freshness=Freshness.from_dict(fresh) if isinstance(fresh, dict) else None,
            stale=_b(data, "stale"),
            raw=data,
        )


@dataclass
class ContentList:
    """Every source on the disk, plus the disk-level consolidation flag."""

    contents: list[Content] = field(default_factory=list)
    consolidating: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def __iter__(self):
        return iter(self.contents)

    def __len__(self) -> int:
        return len(self.contents)

    @property
    def all_processed(self) -> bool:
        return bool(self.contents) and all(row.is_processed for row in self.contents)

    @property
    def failed(self) -> list[Content]:
        return [row for row in self.contents if row.is_failed]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContentList:
        return cls(
            contents=[Content.from_dict(row) for row in _rows(data.get("contents"))],
            consolidating=_b(data, "consolidating"),
            raw=data,
        )


# --------------------------------------------------------------------------- #
# derived memory
# --------------------------------------------------------------------------- #


@dataclass
class Tag:
    """One entry of the disk's controlled tag vocabulary."""

    slug: str = ""
    text: str = ""
    uses: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Tag:
        return cls(slug=_s(data, "slug"), text=_s(data, "text"), uses=_i(data, "uses"), raw=data)


@dataclass
class Fact:
    """One extracted or asserted fact.

    The same shape is returned by the flat memory view, the grouped view and the
    export, so fields that only one of them fills are simply empty elsewhere.
    ``close_kind`` and ``superseded_by`` appear on history entries only — their
    presence is itself the signal that you are looking at a closed fact.
    """

    uuid: str = ""
    text: str = ""
    category: str = ""
    origin: str = ""
    reinforced_count: int = 0
    tags: list[str] = field(default_factory=list)
    subject: str = ""
    predicate: str = ""
    object: str = ""
    priority: int | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    recorded_at: str | None = None
    invalidated: bool = False
    close_kind: str = ""
    superseded_by: str = ""
    folder_path: str = ""
    source_content_uuids: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Fact:
        return cls(
            uuid=_s(data, "uuid"),
            text=_s(data, "text"),
            category=_s(data, "category"),
            origin=_s(data, "origin"),
            reinforced_count=_i(data, "reinforced_count"),
            tags=_strs(data, "tags"),
            subject=_s(data, "subject"),
            predicate=_s(data, "predicate"),
            object=_s(data, "object"),
            priority=_opt_i(data, "priority"),
            valid_from=_opt_s(data, "valid_from"),
            valid_to=_opt_s(data, "valid_to"),
            recorded_at=_opt_s(data, "recorded_at"),
            invalidated=_b(data, "invalidated"),
            close_kind=_s(data, "close_kind"),
            superseded_by=_s(data, "superseded_by"),
            folder_path=_s(data, "folder_path"),
            source_content_uuids=_strs(data, "source_content_uuids"),
            raw=data,
        )


@dataclass
class Memory:
    """What processing produced: enduring facts, the latest summary, the tags."""

    facts: list[Fact] = field(default_factory=list)
    summary: str = ""
    tags: list[Tag] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Memory:
        return cls(
            facts=[Fact.from_dict(row) for row in _rows(data.get("facts"))],
            summary=_s(data, "summary"),
            tags=[Tag.from_dict(row) for row in _rows(data.get("tags"))],
            raw=data,
        )


@dataclass
class FactGroup:
    """One ``(subject, predicate)`` group: what is true now, and what it replaced."""

    subject: str = ""
    predicate: str = ""
    kind: str = ""
    current: list[Fact] = field(default_factory=list)
    history: list[Fact] = field(default_factory=list)
    history_count: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FactGroup:
        return cls(
            subject=_s(data, "subject"),
            predicate=_s(data, "predicate"),
            kind=_s(data, "kind"),
            current=[Fact.from_dict(row) for row in _rows(data.get("current"))],
            history=[Fact.from_dict(row) for row in _rows(data.get("history"))],
            history_count=_i(data, "history_count"),
            raw=data,
        )


@dataclass
class FactGroups:
    """The entity-anchored view of the fact store."""

    groups: list[FactGroup] = field(default_factory=list)
    total_groups: int = 0
    ungrouped: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def __iter__(self):
        return iter(self.groups)

    def __len__(self) -> int:
        return len(self.groups)

    @property
    def truncated(self) -> bool:
        return self.total_groups > len(self.groups)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FactGroups:
        return cls(
            groups=[FactGroup.from_dict(row) for row in _rows(data.get("groups"))],
            total_groups=_i(data, "total_groups"),
            ungrouped=_i(data, "ungrouped"),
            raw=data,
        )


# --------------------------------------------------------------------------- #
# knowledge graph
# --------------------------------------------------------------------------- #


@dataclass
class Subject:
    """One entity the facts are about."""

    name: str = ""
    category: str = ""
    fictional: bool = False
    facts: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Subject:
        return cls(
            name=_s(data, "name"),
            category=_s(data, "category"),
            fictional=_b(data, "fictional"),
            facts=_i(data, "facts"),
            raw=data,
        )


@dataclass
class Edge:
    """One ``subject -> predicate -> object`` relationship."""

    subject: str = ""
    predicate: str = ""
    object: str = ""
    object_text: str = ""
    weight: int = 0
    fact_uuid: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Edge:
        return cls(
            subject=_s(data, "subject"),
            predicate=_s(data, "predicate"),
            object=_s(data, "object"),
            object_text=_s(data, "object_text"),
            weight=_i(data, "weight"),
            fact_uuid=_s(data, "fact_uuid"),
            raw=data,
        )


@dataclass
class SubjectGraph:
    """The knowledge graph as nodes and edges, with its truncation reported."""

    subjects: list[Subject] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    subjects_total: int = 0
    subjects_returned: int = 0
    edges_total: int = 0
    edges_returned: int = 0
    edges_cap: int = 0
    truncated: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SubjectGraph:
        return cls(
            subjects=[Subject.from_dict(row) for row in _rows(data.get("subjects"))],
            edges=[Edge.from_dict(row) for row in _rows(data.get("edges"))],
            subjects_total=_i(data, "subjects_total"),
            subjects_returned=_i(data, "subjects_returned"),
            edges_total=_i(data, "edges_total"),
            edges_returned=_i(data, "edges_returned"),
            edges_cap=_i(data, "edges_cap"),
            truncated=_b(data, "truncated"),
            raw=data,
        )


@dataclass
class GraphResult:
    """The answer to a structural graph query."""

    mode: str = ""
    query: str = ""
    edges: list[Edge] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def __bool__(self) -> bool:
        return bool(self.edges)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphResult:
        return cls(
            mode=_s(data, "mode"),
            query=_s(data, "query"),
            edges=[Edge.from_dict(row) for row in _rows(data.get("edges"))],
            raw=data,
        )


# --------------------------------------------------------------------------- #
# profile / folders / ecosystem
# --------------------------------------------------------------------------- #


@dataclass
class Profile:
    """The disk's generated standing synthesis."""

    body: str = ""
    headline: str = ""
    generated_at: str = ""
    facts_at_gen: int = 0
    gen_count: int = 0
    hash: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        return cls(
            body=_s(data, "body"),
            headline=_s(data, "headline"),
            generated_at=_s(data, "generated_at"),
            facts_at_gen=_i(data, "facts_at_gen"),
            gen_count=_i(data, "gen_count"),
            hash=_s(data, "hash"),
            raw=data,
        )


@dataclass
class MemoryIndex:
    """A compact machine-generated map of what the memory contains."""

    body: str = ""
    generated_at: str = ""
    hash: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryIndex:
        return cls(
            body=_s(data, "body"),
            generated_at=_s(data, "generated_at"),
            hash=_s(data, "hash"),
            raw=data,
        )


@dataclass
class ProfileView:
    """Profile and index together. Either half can be present without the other."""

    profile: Profile | None = None
    index: MemoryIndex | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProfileView:
        profile = data.get("profile")
        index = data.get("index")
        return cls(
            profile=Profile.from_dict(profile) if isinstance(profile, dict) else None,
            index=MemoryIndex.from_dict(index) if isinstance(index, dict) else None,
            raw=data,
        )


@dataclass
class Folder:
    """One virtual folder within a disk."""

    path: str = ""
    name: str = ""
    parent_path: str = ""
    content_count: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Folder:
        return cls(
            path=_s(data, "path"),
            name=_s(data, "name"),
            parent_path=_s(data, "parent_path"),
            content_count=_i(data, "content_count"),
            raw=data,
        )


@dataclass
class Ecosystem:
    """The association graph: sources, tags, facts and the links between them."""

    sources: list[dict[str, Any]] = field(default_factory=list)
    tags: list[Tag] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)
    links: dict[str, list] = field(default_factory=dict)
    facts_total: int = 0
    facts_returned: int = 0
    facts_cap: int = 0
    truncated: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Ecosystem:
        links = _dict(data.get("links"))
        return cls(
            sources=_rows(data.get("sources")),
            tags=[Tag.from_dict(row) for row in _rows(data.get("tags"))],
            facts=[Fact.from_dict(row) for row in _rows(data.get("facts"))],
            links={str(k): v for k, v in links.items() if isinstance(v, list)},
            facts_total=_i(data, "facts_total"),
            facts_returned=_i(data, "facts_returned"),
            facts_cap=_i(data, "facts_cap"),
            truncated=_b(data, "truncated"),
            raw=data,
        )


# --------------------------------------------------------------------------- #
# agent tools
# --------------------------------------------------------------------------- #


@dataclass
class Message:
    """One turn of a stored conversation."""

    uuid: str = ""
    role: str = ""
    text: str = ""
    sort_order: int = 0
    original_timestamp: str | None = None
    original_uuid: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        return cls(
            uuid=_s(data, "uuid"),
            role=_s(data, "role"),
            text=_s(data, "text"),
            sort_order=_i(data, "sort_order"),
            original_timestamp=_opt_s(data, "original_timestamp"),
            original_uuid=_opt_s(data, "original_uuid"),
            raw=data,
        )


@dataclass
class Section:
    """One section of a document that was split at its headings."""

    uuid: str = ""
    name: str = ""
    status: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Section:
        return cls(uuid=_s(data, "uuid"), name=_s(data, "name"), status=_s(data, "status"), raw=data)


@dataclass
class Source:
    """One source's actual body.

    A document fills ``body`` (and ``sections`` when it is a container), where
    ``total`` is the body's full **byte** length and ``offset`` is a byte offset.
    A conversation fills ``messages``, paged by position, where ``total`` is the
    full message count.
    """

    content: Content | None = None
    body: str = ""
    sections: list[Section] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 0
    truncated: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_chat(self) -> bool:
        return bool(self.content and self.content.is_chat)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Source:
        content = data.get("content")
        return cls(
            content=Content.from_dict(content) if isinstance(content, dict) else None,
            body=_s(data, "body"),
            sections=[Section.from_dict(row) for row in _rows(data.get("sections"))],
            messages=[Message.from_dict(row) for row in _rows(data.get("messages"))],
            total=_i(data, "total"),
            offset=_i(data, "offset"),
            limit=_i(data, "limit"),
            truncated=_b(data, "truncated"),
            raw=data,
        )


@dataclass
class GrepHit:
    """One matching message or document body."""

    content_uuid: str = ""
    content_name: str = ""
    content_type: str = ""
    folder_path: str = ""
    message_uuid: str = ""
    sort_order: int = 0
    ts: str = ""
    snippet: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GrepHit:
        return cls(
            content_uuid=_s(data, "content_uuid"),
            content_name=_s(data, "content_name"),
            content_type=_s(data, "content_type"),
            folder_path=_s(data, "folder_path"),
            message_uuid=_s(data, "message_uuid"),
            sort_order=_i(data, "sort_order"),
            ts=_s(data, "ts"),
            snippet=_s(data, "snippet"),
            raw=data,
        )


@dataclass
class GrepResult:
    """Matches for one regex over the stored text. Not ranked — reported."""

    hits: list[GrepHit] = field(default_factory=list)
    pattern: str = ""
    path: str = ""
    limit: int = 0
    truncated: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def __iter__(self):
        return iter(self.hits)

    def __len__(self) -> int:
        return len(self.hits)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GrepResult:
        return cls(
            hits=[GrepHit.from_dict(row) for row in _rows(data.get("hits"))],
            pattern=_s(data, "pattern"),
            path=_s(data, "path"),
            limit=_i(data, "limit"),
            truncated=_b(data, "truncated"),
            raw=data,
        )


@dataclass
class Hub:
    """One entity's centrality in the current graph."""

    name: str = ""
    category: str = ""
    facts: int = 0
    degree_in: int = 0
    degree_out: int = 0
    weighted_degree: int = 0
    pagerank: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Hub:
        return cls(
            name=_s(data, "name"),
            category=_s(data, "category"),
            facts=_i(data, "facts"),
            degree_in=_i(data, "degree_in"),
            degree_out=_i(data, "degree_out"),
            weighted_degree=_i(data, "weighted_degree"),
            pagerank=_f(data, "pagerank"),
            raw=data,
        )


@dataclass
class Hubs:
    """Entity centrality over the current graph. Deterministic."""

    hubs: list[Hub] = field(default_factory=list)
    nodes: int = 0
    edges: int = 0
    top: int = 0
    hubs_total: int = 0
    truncated: bool = False
    path: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def __iter__(self):
        return iter(self.hubs)

    def __len__(self) -> int:
        return len(self.hubs)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Hubs:
        return cls(
            hubs=[Hub.from_dict(row) for row in _rows(data.get("hubs"))],
            nodes=_i(data, "nodes"),
            edges=_i(data, "edges"),
            top=_i(data, "top"),
            hubs_total=_i(data, "hubs_total"),
            truncated=_b(data, "truncated"),
            path=_s(data, "path"),
            raw=data,
        )


@dataclass
class LintSection:
    """One section of the memory audit.

    Each section is fenced independently: one that failed carries ``error`` and a
    ``None`` total while the report as a whole still answered 200. Check
    ``ok`` before trusting a section.
    """

    name: str = ""
    total: int | None = None
    returned: int = 0
    items: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def ok(self) -> bool:
        return not self.error

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> LintSection:
        return cls(
            name=name,
            total=_opt_i(data, "total"),
            returned=_i(data, "returned"),
            items=_rows(data.get("items")),
            error=_s(data, "error"),
            raw=data,
        )


@dataclass
class LintReport:
    """A read-only audit of the disk's derived memory."""

    disk: str = ""
    generated_at: str = ""
    path: str = ""
    limit: int = 0
    sections: dict[str, LintSection] = field(default_factory=dict)
    totals: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def failed_sections(self) -> list[LintSection]:
        """The sections that could not be computed. A 200 does not mean all seven ran."""
        return [section for section in self.sections.values() if not section.ok]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LintReport:
        sections = _dict(data.get("sections"))
        return cls(
            disk=_s(data, "disk"),
            generated_at=_s(data, "generated_at"),
            path=_s(data, "path"),
            limit=_i(data, "limit"),
            sections={
                str(name): LintSection.from_dict(str(name), _dict(body)) for name, body in sections.items()
            },
            totals=_dict(data.get("totals")),
            raw=data,
        )


@dataclass
class ExtractedFact:
    """One fact a dry-run extraction would have produced. Nothing was stored.

    ``temporal_confidence`` says how precisely the text stated the time (1.00 a
    full date, 0.90 a month, 0.85 a bare year, 0.65 "late 2019", 0.35 "recently",
    0.00 no signal), and ``temporal_source_text`` is the exact words that carried
    it. Below 0.85 the date is deliberately left empty.
    """

    text: str = ""
    subject: str = ""
    predicate: str = ""
    object: str = ""
    category: str = ""
    valid_from: str | None = None
    valid_to: str | None = None
    temporal_confidence: float = 0.0
    temporal_source_text: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractedFact:
        return cls(
            text=_s(data, "text"),
            subject=_s(data, "subject"),
            predicate=_s(data, "predicate"),
            object=_s(data, "object"),
            category=_s(data, "category"),
            valid_from=_opt_s(data, "valid_from"),
            valid_to=_opt_s(data, "valid_to"),
            temporal_confidence=_f(data, "temporal_confidence"),
            temporal_source_text=_s(data, "temporal_source_text"),
            raw=data,
        )


@dataclass
class ExtractPreview:
    """What extraction *would* remember from a piece of text."""

    facts: list[ExtractedFact] = field(default_factory=list)
    dropped: int = 0
    chars: int = 0
    truncated: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def __iter__(self):
        return iter(self.facts)

    def __len__(self) -> int:
        return len(self.facts)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractPreview:
        return cls(
            facts=[ExtractedFact.from_dict(row) for row in _rows(data.get("facts"))],
            dropped=_i(data, "dropped"),
            chars=_i(data, "chars"),
            truncated=_b(data, "truncated"),
            raw=data,
        )


@dataclass
class ConsolidationRun:
    """One consolidation fold, after the fact.

    ``diff`` is present when a single run is read; ``plan`` only when it was
    requested — and the plan is computed, never executed.
    """

    uuid: str = ""
    seed_fact_uuid: str = ""
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int = 0
    tier_counts: dict[str, Any] = field(default_factory=dict)
    facts_closed: int = 0
    facts_rewritten: int = 0
    contested: int = 0
    clusters: int = 0
    superseded: int = 0
    diff: dict[str, Any] = field(default_factory=dict)
    plan: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConsolidationRun:
        return cls(
            uuid=_s(data, "uuid"),
            seed_fact_uuid=_s(data, "seed_fact_uuid"),
            started_at=_s(data, "started_at"),
            finished_at=_s(data, "finished_at"),
            duration_ms=_i(data, "duration_ms"),
            tier_counts=_dict(data.get("tier_counts")),
            facts_closed=_i(data, "facts_closed"),
            facts_rewritten=_i(data, "facts_rewritten"),
            contested=_i(data, "contested"),
            clusters=_i(data, "clusters"),
            superseded=_i(data, "superseded"),
            diff=_dict(data.get("diff")),
            plan=_dict(data.get("plan")),
            raw=data,
        )


@dataclass
class ConsolidationRuns:
    """Consolidation history, newest first. Counts only — a fold's diff is per-run."""

    runs: list[ConsolidationRun] = field(default_factory=list)
    returned: int = 0
    limit: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def __iter__(self):
        return iter(self.runs)

    def __len__(self) -> int:
        return len(self.runs)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConsolidationRuns:
        return cls(
            runs=[ConsolidationRun.from_dict(row) for row in _rows(data.get("runs"))],
            returned=_i(data, "returned"),
            limit=_i(data, "limit"),
            raw=data,
        )
