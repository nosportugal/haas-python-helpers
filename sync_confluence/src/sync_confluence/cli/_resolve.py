"""Resolve the docs location (directory or files) from CLI arguments."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_DOCS_CANDIDATES = ("docs", "documentation", "doc")
_SYNC_MODE_DIR = "directory"
_SYNC_MODE_FILES = "files"


@dataclass
class _DocsInfo:
    """Resolved docs location and mode."""

    root: Path
    mode: str
    files: list[Path]


def _resolve_docs_root(
    args: argparse.Namespace,
) -> tuple[Optional[Path], str, list[Path]]:
    """Determine docs_root, sync_mode and docs_files from args."""
    if getattr(args, "docs_files", None):
        docs_files = [Path(docs_file_path) for docs_file_path in args.docs_files]
        return Path.cwd(), _SYNC_MODE_FILES, docs_files
    if args.docs_dir:
        docs_root = Path(args.docs_dir)
        if not docs_root.is_dir():
            log.error("Docs directory not found: %s", docs_root)
            return None, _SYNC_MODE_DIR, []
        return docs_root, _SYNC_MODE_DIR, []
    for candidate in _DOCS_CANDIDATES:
        candidate_path = Path(candidate)
        if candidate_path.is_dir():
            return candidate_path, _SYNC_MODE_DIR, []
    log.error(
        "Could not find a docs directory. Pass --docs-dir or create one of: %s",
        ", ".join(f"{dir_name}/" for dir_name in _DOCS_CANDIDATES),
    )
    return None, _SYNC_MODE_DIR, []
