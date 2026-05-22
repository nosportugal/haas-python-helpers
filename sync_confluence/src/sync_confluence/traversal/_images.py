"""Local image reference extraction and attachment filename helpers."""

from __future__ import annotations

import re
from types import MappingProxyType
from typing import Mapping

# Regex to find ![alt](path) references in raw Markdown.
_LOCAL_IMAGE_RE = re.compile(r"!\[.*?\]\(([^)]+)\)")

# Content-type registry for all attachment types used by sync_confluence.
# SVG is produced by mermaid rendering only; it is not a valid local image
# upload extension (see SUPPORTED_LOCAL_IMAGE_EXTENSIONS below).
CONTENT_TYPES: Mapping[str, str] = MappingProxyType(
    {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
    }
)

# Subset of extensions eligible for local image uploads.
SUPPORTED_LOCAL_IMAGE_EXTENSIONS: frozenset[str] = frozenset((".png", ".jpg", ".jpeg"))


def extract_local_image_paths(text: str) -> list[str]:
    """Return relative image paths found in raw Markdown *text*.

    External URLs (``http://``, ``https://``, ``#``, or any path containing
    ``://``) are excluded.
    """
    paths: list[str] = []
    for match in _LOCAL_IMAGE_RE.finditer(text):
        path = match.group(1).strip()
        if path.startswith(("http://", "https://", "#")) or "://" in path:
            continue
        paths.append(path)
    return paths


def local_image_attachment_filename(rel_path: str) -> str:
    """Convert a relative image path to a safe Confluence attachment filename.

    Strips a leading ``./``, then replaces ``/`` and backslash with ``-``.

    Examples::

        "images/logo.png"   to   "images-logo.png"
        "./assets/fig.jpg"  to   "assets-fig.jpg"
    """
    path = rel_path.lstrip("./") if rel_path.startswith("./") else rel_path
    return path.replace("/", "-").replace("\\", "-")


def attachment_content_type(filename: str) -> str:
    """Return the MIME content-type for *filename* based on its extension.

    Falls back to ``"application/octet-stream"`` for unknown extensions.
    """
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""  # noqa: WPS221
    ext_key = f".{suffix}"
    return CONTENT_TYPES.get(ext_key, "application/octet-stream")  # noqa: WPS221
