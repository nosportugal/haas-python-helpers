"""Compute safe Confluence attachment filenames from local paths.

An attachment name is the image path relative to the Markdown file's parent,
flattened into a single filename so identically-named images in different
subdirectories do not collide on the same page.  Disallowed characters are
replaced with ``_`` and parent-directory hops (``..``) become ``PAR``.
"""

from __future__ import annotations

import re
from os.path import relpath
from pathlib import Path

_DISALLOWED_RE = re.compile(r"[^-0-9A-Za-z_.]")


def _safe_part(part: str) -> str:
    if part == "..":
        return "PAR"
    return _DISALLOWED_RE.sub("_", part)


def attachment_name(path: Path, base: Path) -> str:
    """Return a flattened, Confluence-safe attachment name for *path*."""
    relative = Path(relpath(path, base))
    return "_".join(_safe_part(part) for part in relative.parts)
