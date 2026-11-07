"""Page attachment value object shared by converters and page upload."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Attachment:
    """A page attachment to upload alongside a Confluence page.

    For local images *path* is the absolute source path; *name* is the
    flattened attachment filename used for the ``ri:filename`` reference and
    the upload.

    For rendered diagrams (e.g. Mermaid SVG) *path* is ``None`` and
    *raw_bytes* / *content_type* carry the in-memory payload.
    """

    name: str
    path: Optional[Path] = None
    raw_bytes: Optional[bytes] = None
    content_type: Optional[str] = None
