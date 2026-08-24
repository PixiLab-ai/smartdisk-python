"""SmartDisk — the official Python SDK for the SmartDisk memory engine.

Give it conversations and documents; it organises them into a searchable disk and
hands back grounded context with citations to the source.

```python
from smartdisk import SmartDisk

client = SmartDisk(api_key="sd_...")
disk = client.disks.create(name="Research notes", slug="research")

client.imports.document(disk, body="We moved the launch to March.", name="planning.md")
client.imports.wait_until_processed(disk)

print(client.retrieve(disk, "when is the launch?").block)
```

Docs: https://smartdisk.pixilab.ai/docs
"""

from __future__ import annotations

__version__ = "0.1.0"

from .client import SmartDisk
from .errors import (
    AccessRequiredError,
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    ForbiddenError,
    NotAvailableError,
    NotFoundError,
    RateLimitError,
    ServerError,
    SessionRequiredError,
    SmartDiskError,
    TooLargeError,
    UnprocessableError,
    UpstreamError,
)
from .models import (
    Answer,
    ChatImport,
    Citation,
    ConsolidationRun,
    ConsolidationRuns,
    Content,
    ContentList,
    Disk,
    DiskSettings,
    DocumentImport,
    Ecosystem,
    Edge,
    Explain,
    ExtractedFact,
    ExtractPreview,
    Fact,
    FactGroup,
    FactGroups,
    Folder,
    Freshness,
    GraphResult,
    GrepHit,
    GrepResult,
    Hub,
    Hubs,
    Ledger,
    LintReport,
    LintSection,
    Memory,
    MemoryIndex,
    Message,
    OcrResult,
    Profile,
    ProfileView,
    Retrieval,
    Section,
    Source,
    StableBlock,
    Subject,
    SubjectGraph,
    SyncCursor,
    Tag,
    UrlImport,
    Whoami,
)

__all__ = [
    "__version__",
    "SmartDisk",
    # errors
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
    # models
    "Disk",
    "DiskSettings",
    "Whoami",
    "ChatImport",
    "DocumentImport",
    "UrlImport",
    "OcrResult",
    "SyncCursor",
    "Citation",
    "Explain",
    "StableBlock",
    "Ledger",
    "Retrieval",
    "Answer",
    "Content",
    "ContentList",
    "Freshness",
    "Fact",
    "FactGroup",
    "FactGroups",
    "Memory",
    "Tag",
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
