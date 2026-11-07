"""Derive Confluence page titles from Markdown file paths."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def _extract_h1_or_none(md_path: Path) -> Optional[str]:
    """Return the first H1 heading text from *md_path*, or ``None``."""
    file_content = md_path.read_text(encoding="utf-8")
    h1_match = _H1_RE.search(file_content)
    return h1_match.group(1).strip() if h1_match else None


def derive_title(md_path: Path, docs_root: Path, root_title: Optional[str]) -> str:
    """Derive a Confluence page title from a Markdown file path.

    - Root README.md: use *root_title* or extract the first H1.
    - Other README.md: extract the first H1; fall back to title-casing the
      parent directory name when no H1 is present.
    - Non-README files: extract the first H1; fall back to title-casing the
      file stem when no H1 is present.
    """
    is_readme = md_path.name == "README.md"
    if is_readme and md_path.parent == docs_root:
        return root_title or _extract_h1_or_none(md_path) or "Documentation"
    if is_readme:
        return (
            _extract_h1_or_none(md_path)
            or md_path.parent.name.replace("-", " ").title()
        )
    return _extract_h1_or_none(md_path) or md_path.stem.replace("-", " ").title()
