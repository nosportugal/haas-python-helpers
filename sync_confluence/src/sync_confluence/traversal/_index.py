"""Filesystem-only page-title index for internal link resolution.

The index maps each Markdown file's absolute path to the Confluence page
title it will be synced under, replicating the walker's title rules without
any API calls (so it also works in dry-run).  Files whose titles collide are
excluded, mirroring the title-collision skip behaviour during the sync pass.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from sync_confluence.converter import derive_title

log = logging.getLogger(__name__)

_README = "README.md"


def _title_for(md_file: Path, docs_root: Path, root_title: Optional[str]) -> str:
    if md_file.name == _README and md_file.parent == docs_root:
        return derive_title(md_file, docs_root, root_title)
    return derive_title(md_file, docs_root, None)


def _drop_duplicates(
    titles: dict[Path, str], counts: dict[str, int]
) -> dict[Path, str]:
    index: dict[Path, str] = {}
    for path, title in titles.items():
        if counts[title] > 1:
            log.warning(
                "Duplicate page title '%s' (%s); excluding from link index",
                title,
                path,
            )
            continue
        index[path] = title
    return index


def build_doc_index(
    docs_root: Path, root_title: Optional[str], md_files: list[Path]
) -> dict[Path, str]:
    """Map each Markdown file to its page title, excluding duplicate titles."""
    titles: dict[Path, str] = {}
    counts: dict[str, int] = {}
    for md_file in md_files:
        title = _title_for(md_file, docs_root, root_title)
        titles[md_file.resolve()] = title
        counts[title] = counts.get(title, 0) + 1
    return _drop_duplicates(titles, counts)
