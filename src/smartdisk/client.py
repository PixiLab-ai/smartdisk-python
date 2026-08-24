"""The client: one object, four namespaces, and retrieval on the front door."""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

import httpx

from ._http import DEFAULT_BASE_URL, DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT, Transport
from ._util import DiskRef, disk_slug_or_none, disk_uuid_or_none, prune
from .errors import NotFoundError
from .models import Retrieval, Whoami
from .resources import Disks, Imports, Memory, Tools

__all__ = ["SmartDisk"]

RETRIEVE_TIMEOUT = 120.0


class SmartDisk:
    """A SmartDisk API client.

    ```python
    from smartdisk import SmartDisk

    client = SmartDisk(api_key="sd_...")
    disk = client.disks.create(name="Support bot", slug="support-bot")

    client.imports.chat(disk, [
        {"role": "user", "content": "I'm on the Pro plan and I prefer email."},
        {"role": "assistant", "content": "Noted — email it is."},
    ])
    client.imports.wait_until_processed(disk)

    context = client.retrieve(disk, "how does this customer like to be contacted?")
    print(context.block)
    ```

    Args:
        api_key: Your key, minted on the API keys page of the web app. Falls back
            to ``SMARTDISK_API_KEY``.
        base_url: Override for a staging or test deployment. Falls back to
            ``SMARTDISK_BASE``, then the hosted API.
        timeout: Default request timeout in seconds. Individual calls raise it
            where the work is longer — retrieval, answers, imports.
        max_retries: How many times to retry a 429/502/503/504 or a transport
            error, with exponential backoff and jitter. ``0`` disables retrying.
        http_client: Bring your own ``httpx.Client`` (proxies, custom transport,
            a mock transport in tests). The SDK will not close a client you own.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx.Client | None = None,
    ):
        key = api_key or os.environ.get("SMARTDISK_API_KEY", "")
        base = base_url or os.environ.get("SMARTDISK_BASE") or DEFAULT_BASE_URL

        from . import __version__

        self._transport = Transport(
            key,
            base_url=base,
            timeout=timeout,
            max_retries=max_retries,
            user_agent=f"smartdisk-python/{__version__}",
            http_client=http_client,
        )
        self._slug_cache: dict[str, str] = {}

        self.disks = Disks(self._transport, self._resolve_disk)
        self.imports = Imports(self._transport, self._resolve_disk)
        self.memory = Memory(self._transport, self._resolve_disk)
        self.tools = Tools(self._transport, self._resolve_disk)

    # --- lifecycle -------------------------------------------------------- #

    @property
    def base_url(self) -> str:
        return self._transport.base_url

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._transport.close()

    def __enter__(self) -> SmartDisk:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # --- disk references -------------------------------------------------- #

    def _resolve_disk(self, disk: DiskRef) -> str:
        """A uuid for anything a caller may pass as a disk.

        A :class:`~smartdisk.Disk` or a uuid string is used as-is. A slug is
        looked up once through the disk listing and cached for the client's life.
        """
        uuid = disk_uuid_or_none(disk)
        if uuid:
            return uuid

        slug = disk_slug_or_none(disk)
        if not slug:
            raise ValueError("a disk is required — pass a Disk, a disk uuid, or a disk slug")
        if slug in self._slug_cache:
            return self._slug_cache[slug]

        found = self.disks.find(slug)
        if found is None or not found.uuid:
            raise NotFoundError(
                f"no disk with slug {slug!r} belongs to this API key",
                status=404,
                code="disk_not_found",
            )
        self._slug_cache[slug] = found.uuid
        return found.uuid

    # --- the core call ---------------------------------------------------- #

    def retrieve(
        self,
        disk: DiskRef,
        query: str,
        *,
        path: str | None = None,
        context_tokens: int | None = None,
        categories: Sequence[str] | None = None,
        tags: Sequence[str] | None = None,
        since: str | None = None,
        until: str | None = None,
        min_score: float | None = None,
        graph_expand: bool | None = None,
        graph_hops: int | None = None,
        expand: bool | None = None,
        expand_max: int | None = None,
        recency: bool | None = None,
        exclude: Sequence[str] | None = None,
        session_id: str | None = None,
        dedup_turns: int | None = None,
        explain: bool | None = None,
        candidates: int | None = None,
        drill: bool | None = None,
        fictional: bool | None = None,
    ) -> Retrieval:
        """Search a disk's memory and get back ready-to-prompt context.

        **This is the core of the API.** Retrieval is hybrid (dense + keyword)
        with reranking and a coarse-to-fine drill, but there is no model in the
        loop: you get a packed, numbered ``block`` plus the ``citations`` behind
        each ``[n]``, and you feed it into your own model however you like. For a
        written answer instead, use :meth:`Memory.ask`.

        Retrieval refuses to pad. Everything has to clear ``min_score`` — the
        calibrated default floor is ``0.35`` — and if nothing clears it you get an
        empty block rather than the best few pieces of noise. Pass ``min_score=-1``
        to remove the floor and take the raw top-N.

        Args:
            disk: The disk to search — a ``Disk``, a uuid, or a slug.
            query: What to search the memory for.
            path: Folder subtree to scope to. ``"/"`` (the default) is the whole
                disk, ``"/research"`` is that folder and everything under it.
            context_tokens: Cap on the size of the returned block.
            categories: Restrict the **fact** layer to these categories. Passages
                and summaries are unaffected.
            tags: Restrict to memory carrying any of these tags. Unlike
                ``categories`` this narrows **every** layer. Discover what is
                filterable with :meth:`Memory.tags`.
            since: Only memory created at or after this RFC 3339 instant.
            until: Only memory created at or before this RFC 3339 instant.
            min_score: Relevance floor. ``0``/omitted uses the calibrated default,
                a negative value removes it, a positive value sets your own.
            graph_expand: When the query names an entity, also inject connected
                entities' facts through the knowledge graph. Adds breadth.
            graph_hops: How far ``graph_expand`` walks (default 1).
            expand: Rewrite the query into a few diverse searches — paraphrases,
                sub-questions, one hypothetical answer — and merge the results.
                One fast model call, better recall on vague or multi-part asks.
            expand_max: Cap on expanded queries including the original (default 4).
            recency: Prefer fresh conversation via a soft time decay on chat
                passages. A bounded multiplier, never a cutoff.
            exclude: ``object_uuid`` values already in your context — skipped this
                turn. See :attr:`Retrieval.object_uuids`.
            session_id: Names an ongoing conversation so the server can remember
                what it already served it. Needs ``dedup_turns`` to do anything.
            dedup_turns: How many recent turns of that session to cool a served
                memory for. Capped at 32.
            explain: Attach a per-citation scoring trace. Purely diagnostic —
                results are byte-identical with it on, so it is safe in production.
            candidates: How many candidates reach the reranker. Lower is faster.
            drill: Set ``False`` to skip the coarse-to-fine second pass.
            fictional: Tri-state filter on the fact layer — ``None`` both,
                ``False`` real only, ``True`` fictional only.

        ``POST /sd/disks/:uuid/retrieve``
        """
        body: dict[str, Any] = prune(
            {
                "query": query,
                "path": path,
                "context_tokens": context_tokens,
                "categories": list(categories) if categories else None,
                "tags": list(tags) if tags else None,
                "since": since,
                "until": until,
                "min_score": min_score,
                "graph_expand": graph_expand,
                "graph_hops": graph_hops,
                "expand": expand,
                "expand_max": expand_max,
                "recency": recency,
                "exclude": list(exclude) if exclude else None,
                "session_id": session_id,
                "dedup_turns": dedup_turns,
                "explain": explain,
                "candidates": candidates,
                "drill": drill,
                "fictional": fictional,
            }
        )
        url = self._transport.disk_url(self._resolve_disk(disk), "retrieve")
        payload = self._transport.post(url, json=body, timeout=RETRIEVE_TIMEOUT)
        return Retrieval.from_dict(payload if isinstance(payload, dict) else {})

    # --- identity --------------------------------------------------------- #

    def whoami(self) -> Whoami:
        """Which server this key is talking to, and how it authenticated.

        Useful as a start-up check when a client can be pointed at more than one
        deployment: confirm the ``env`` before writing memory into it.

        ``GET /sd/whoami``
        """
        payload = self._transport.get(self._transport.url("whoami"))
        return Whoami.from_dict(payload if isinstance(payload, dict) else {})
