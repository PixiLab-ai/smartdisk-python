# smartdisk-python

The official Python SDK for **[SmartDisk](https://smartdisk.pixilab.ai)** — a memory
engine. You give it conversations and documents; it organises them into a searchable
**disk** and answers questions grounded in what you stored, with citations back to the
source.

- Full API reference: <https://smartdisk.pixilab.ai/docs>
- Sibling SDKs: [smartdisk-mcp](https://github.com/PixiLab-ai/smartdisk-mcp) (Model Context Protocol server)

---

## Install

**Not on PyPI yet.** Install from source:

```bash
pip install git+https://github.com/PixiLab-ai/smartdisk-python.git
```

Or from a clone, for hacking on it:

```bash
git clone https://github.com/PixiLab-ai/smartdisk-python.git
cd smartdisk-python
pip install -e ".[dev]"
```

Python 3.10+. The only runtime dependency is `httpx`.

## Authenticate

Every call needs an API key, minted on the **API keys** page of the web app and shown
once at creation. A key acts as its owner and reaches only that owner's disks.

```python
from smartdisk import SmartDisk

client = SmartDisk(api_key="sd_...")  # or set SMARTDISK_API_KEY
```

`base_url` (or `SMARTDISK_BASE`) points the client at a self-hosted server.

> Access is granted per account. If every call raises `AccessRequiredError`, the account
> has not been enabled for SmartDisk yet — retrying will not fix it.

---

## Three calls

Import something, wait for it to process, ask about it.

```python
from smartdisk import SmartDisk

client = SmartDisk(api_key="sd_...")
disk = client.disks.create(name="Support bot", slug="support-bot")

# 1. import — a conversation, appended to a thread by name
client.imports.chat(
    disk,
    name="ticket-4471",
    messages=[
        {"role": "user", "content": "I'm on the Pro plan and I'd rather be emailed than called."},
        {"role": "assistant", "content": "Noted — email only, and I've flagged the Pro plan."},
    ],
)
client.imports.wait_until_processed(disk)

# 2. retrieve — ready-to-prompt context, no model in the loop
context = client.retrieve(disk, "how does this customer want to be contacted?")
print(context.block)  # numbered [1..n] passages for your own prompt
print(context.citations[0].content_name)

# 3. ask — the server retrieves, then writes one grounded answer
answer = client.memory.ask(disk, "what plan are they on, and how do they prefer contact?")
print(answer.answer)
```

`retrieve` and `ask` are the same retrieval; `ask` spends one extra model call to write
the answer. Reach for `retrieve` when your own model will reason over the passages.

---

## What you should know before building on it

**Import is asynchronous.** Content moves `queued → processing → processed`, so a read
straight after an import reads an empty disk. `client.imports.wait_until_processed(disk)`
polls until it settles; `client.memory.contents(disk)` is the raw status view.

**A conversation is an append-only thread; a document is a path.** Re-importing a
conversation with the same `name` appends to the same thread (messages carrying a `uuid`
are deduplicated individually). Re-importing a document at the same `(folder_path, name)`
is an upsert — unchanged bodies skip themselves, so syncing a folder is just POSTing
every file.

**Retrieval refuses to pad.** Everything has to clear a relevance floor (calibrated
default `0.35`), and if nothing clears it you get an empty block rather than the best few
pieces of noise. `Retrieval` is falsy when it found nothing:

```python
context = client.retrieve(disk, "something the disk never heard of")
if not context:
    print("nothing relevant stored")
```

Pass `min_score=-1` to remove the floor entirely and take the raw top-N.

**`stable` rides every retrieval.** The disk's standing profile and memory index come back
on each response as one prompt block that is byte-identical until its `hash` changes — pin
it at the end of your system prompt and re-inject only on a new hash.

```python
cached_hash, cached_block = "", ""

context = client.retrieve(disk, query)
if context.stable and context.stable.hash != cached_hash:
    cached_hash, cached_block = context.stable.hash, context.stable.block
```

**Don't repeat yourself across turns.** An agent that retrieves every turn keeps getting
the same winner back. Either carry the state yourself with `exclude`, or let the server
carry it with `session_id` + `dedup_turns`:

```python
seen: list[str] = []
context = client.retrieve(disk, query, exclude=seen)
seen += context.object_uuids

# or, server-side:
context = client.retrieve(disk, query, session_id="chat-8412", dedup_turns=8)
```

**Scope with `path`.** Contents live under a virtual folder path (imports land in
`/imports`). Every retrieval and most tools take a `path` that scopes to a subtree — it is
faster and sharper than searching everything.

---

## Errors

Every failure is a typed exception carrying the server's own `code`, its `detail`, and the
HTTP `status`.

```python
from smartdisk import AccessRequiredError, TooLargeError, UnprocessableError

try:
    client.imports.url(disk, "https://example.com/article")
except UnprocessableError as exc:
    # blocked | no_content | no_transcript | unavailable
    print("could not read that page:", exc.code)

try:
    client.tools.export(disk, format="csv")
except TooLargeError as exc:
    print(f"{exc.facts_total} facts, cap {exc.max_facts} — narrow it with path=")
```

| Exception | HTTP | When |
|---|---|---|
| `BadRequestError` | 400 | Malformed request, bad pattern, empty text, bad timestamp. |
| `AuthenticationError` | 401 | Key missing, malformed, or revoked. |
| `ForbiddenError` | 403 | The disk is not yours. |
| `AccessRequiredError` | 403 | The account has no SmartDisk access. Retrying will not help. |
| `SessionRequiredError` | 403 | Key management needs a browser session, not a key. |
| `NotFoundError` | 404 | No such disk, source, or run **on this disk**. |
| `TooLargeError` | 413 | More memory than the endpoint will answer for. Narrow with `path`. |
| `UnprocessableError` | 422 | A URL that couldn't be fetched or had no transcript. |
| `RateLimitError` | 429 | Too many requests — retried automatically first. |
| `ServerError` | 500 | `ingest_failed`, `chat_failed`. |
| `UpstreamError` | 502 | OCR or extraction failed. Retryable. |
| `NotAvailableError` | 503 | The feature isn't deployed on this server yet. Not an outage. |
| `APIConnectionError` / `APITimeoutError` | — | The server could not be reached in time. |

`429`, `502`, `503`, `504` and transport errors are retried automatically (2 attempts,
exponential backoff with jitter, `Retry-After` honoured). `500` is **not** retried — its
side effects are not visible from the outside. Tune with `SmartDisk(..., max_retries=0)`.

---

## The full surface

Every method maps to exactly one documented route. `disk` is always a `Disk`, a disk
uuid, or a disk slug.

### `client.disks`

| Method | Route |
|---|---|
| `create(name, slug=, description=)` | `POST /sd/disks` — idempotent on slug |
| `list()` | `GET /sd/disks` |
| `find(slug)` | client-side filter over `list()` |
| `delete(disk)` | `DELETE /sd/disks/:uuid` |
| `settings(disk)` | `GET /sd/disks/:uuid/settings` |
| `update_settings(disk, about=, paused=)` | `PUT /sd/disks/:uuid/settings` |

### `client.imports`

| Method | Route |
|---|---|
| `chat(disk, messages, name=, folder_path=, persona=, source=, aliases=, disk_name=)` | `POST /sd/import/chatml` (bare slug — resolves **or creates** the disk) · `POST /sd/disks/:uuid/import/chatml` (uuid) |
| `document(disk, path=/body=/data=/body_b64=, name=, title=, folder_path=, source=, format=)` | `POST /sd/disks/:uuid/import/doc` |
| `url(disk, url, name=)` | `POST /sd/disks/:uuid/import/url` |
| `ocr(path=/data=/image_b64=, format=)` | `POST /sd/ocr` |
| `last(disk)` | `GET /sd/disks/:uuid/import/last` — the incremental-sync cursor |
| `retry(disk, content_uuid)` | `POST /sd/disks/:uuid/contents/:cuuid/retry` |
| `wait_until_processed(disk, ...)` | polls `GET /sd/disks/:uuid/contents` |

### `client.retrieve(disk, query, ...)`

`POST /sd/disks/:uuid/retrieve`. Options: `path`, `context_tokens`, `categories`, `tags`,
`since`, `until`, `min_score`, `graph_expand`, `graph_hops`, `expand`, `expand_max`,
`recency`, `exclude`, `session_id`, `dedup_turns`, `explain`, `candidates`, `drill`,
`fictional`.

### `client.memory`

| Method | Route |
|---|---|
| `ask(disk, query, model=, language=, history=, ...)` | `POST /sd/disks/:uuid/chat` |
| `contents(disk)` | `GET /sd/disks/:uuid/contents` |
| `facts(disk)` | `GET /sd/disks/:uuid/memory` |
| `groups(disk)` | `GET /sd/disks/:uuid/groups` |
| `subjects(disk, limit=)` | `GET /sd/disks/:uuid/subjects` |
| `tags(disk, path=)` | `GET /sd/disks/:uuid/tags` |
| `profile(disk)` | `GET /sd/disks/:uuid/profile` |
| `regenerate_profile(disk)` | `POST /sd/disks/:uuid/profile/regen` |
| `ecosystem(disk, limit=)` | `GET /sd/disks/:uuid/ecosystem` |
| `graph(disk, q, depth=)` | `GET /sd/disks/:uuid/graph-query` |
| `delete_content(disk, content_uuid)` | `DELETE /sd/disks/:uuid/contents/:cuuid` |
| `move_content(disk, content_uuid, folder_path)` | `POST /sd/disks/:uuid/contents/:cuuid/move` |
| `folders(disk)` | `GET /sd/disks/:uuid/folders` |
| `create_folder(disk, path)` | `POST /sd/disks/:uuid/folders` |
| `delete_folder(disk, path)` | `DELETE /sd/disks/:uuid/folders` |
| `aliases(disk)` / `set_aliases(disk, aliases)` | `GET`/`PUT /sd/disks/:uuid/aliases` |
| `content_aliases(disk, cuuid)` / `set_content_aliases(disk, cuuid, aliases)` | `GET`/`PUT /sd/disks/:uuid/contents/:cuuid/aliases` |
| `remember(disk, text, subject=, predicate=, object=, category=, priority=)` | `POST /sd/disks/:uuid/remember` |
| `forget(disk, fact_uuid)` | `POST /sd/disks/:uuid/forget` |
| `feedback(disk, fact_uuids, score)` | `POST /sd/disks/:uuid/feedback` |
| `reprioritize(disk, fact_uuid, priority)` | `POST /sd/disks/:uuid/reprioritize` |

### `client.tools` — read-only

| Method | Route |
|---|---|
| `read(disk, content_uuid, offset=, limit=)` | `GET /sd/disks/:uuid/contents/:cuuid` |
| `grep(disk, pattern, case_insensitive=, limit=, path=)` | `GET /sd/disks/:uuid/grep` |
| `export(disk, format=, include=, path=)` | `GET /sd/disks/:uuid/export` — raw file bytes |
| `hubs(disk, top=, path=)` | `GET /sd/disks/:uuid/hubs` |
| `lint(disk, path=, limit=)` | `GET /sd/disks/:uuid/lint` |
| `extract_preview(disk, text, aliases=)` | `POST /sd/disks/:uuid/extract-preview` |
| `consolidation_runs(disk, limit=)` | `GET /sd/disks/:uuid/consolidation/runs` |
| `consolidation_run(disk, run_uuid, plan=)` | `GET /sd/disks/:uuid/consolidation/runs/:run` |

### `client.whoami()`

`GET /sd/whoami` — which server the key is talking to. Worth checking at start-up when a
client can be pointed at more than one deployment.

---

## Recipes

**Sync a folder of documents.** Unchanged files skip themselves server-side, so this is
cheap to re-run; compare `content_hash` locally first if you want to skip the upload too.

```python
from pathlib import Path

for file in Path("./notes").rglob("*.md"):
    client.imports.document(disk, path=file, folder_path=f"/notes/{file.parent.name}")
```

**Keep a growing chat log in step.** The cursor lives with the disk, not your client, so
it stays correct even if the disk is rebuilt.

```python
cursor = client.imports.last(disk)
new = [m for m in log if cursor.empty or m["timestamp"] > cursor.original_timestamp]
if new:
    client.imports.chat(disk, new, name=cursor.name or "chat")
```

**Follow a citation back to its source.**

```python
context = client.retrieve(disk, "why did we move the launch?")
top = context.citations[0]
source = client.tools.read(disk, top.content_uuid)
print(source.body[:2000] if not source.is_chat else source.messages[:5])
```

**Find an exact string.** Semantic search understands meaning, not tokens, so an error
code or an identifier can slip past it. `grep` is a regex over the stored bodies (RE2 — no
backreferences, no lookaround).

```python
for hit in client.tools.grep(disk, r"ERR_[A-Z_]+", case_insensitive=False):
    print(hit.content_name, "—", hit.snippet)
```

**Teach it something directly, and un-teach it.**

```python
fact = client.memory.remember(
    disk, "Alex works at Northwind Trading.", subject="alex", predicate="works_at", object="northwind"
)
client.memory.reprioritize(disk, fact, 90)
client.memory.forget(disk, fact)  # a bitemporal close, not a delete
```

**See what a source *would* teach it, before committing.** `extract_preview` runs the real
extraction prompt and stores nothing.

```python
preview = client.tools.extract_preview(disk, open("draft.md").read())
for fact in preview:
    print(fact.text, "|", fact.valid_from, "|", fact.temporal_source_text)
```

---

## Development

```bash
pip install -e ".[dev]"
pytest          # offline: every test runs against a mock transport
ruff check .
```

The test suite never opens a socket and never needs an API key. It asserts on the exact
request each method builds — method, URL, query string, JSON body — and on how each
documented error code maps to an exception.

## License

MIT. See [LICENSE](LICENSE).
