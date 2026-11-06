"""Filesystem → Confluence traversal.

Public surface:

- :class:`SyncContext` — connection + sync configuration.
- :class:`SyncResult` — accumulated outcome (page map, expected titles/paths,
  skipped titles and per-action counts).
- :func:`sync_directory` — recursive directory walk.
- :func:`sync_files` — flat list of Markdown files.
- :func:`find_mmdc`, :func:`make_mermaid_renderer` — Mermaid CLI renderer setup.
"""

from sync_confluence.confluence.sync_cli import SyncResult
from sync_confluence.markdown.traversal._diagrams import (
    find_mmdc,
    make_mermaid_renderer,
)
from sync_confluence.markdown.traversal._index import build_doc_index
from sync_confluence.markdown.traversal._state import SyncContext
from sync_confluence.markdown.traversal._walker import sync_directory, sync_files

__all__ = [
    "SyncContext",
    "SyncResult",
    "build_doc_index",
    "find_mmdc",
    "make_mermaid_renderer",
    "sync_directory",
    "sync_files",
]
