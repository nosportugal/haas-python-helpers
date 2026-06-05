"""Filesystem → Confluence traversal.

Public surface:

- :class:`SyncContext` — connection + sync configuration.
- :class:`SyncResult` — accumulated outcome (page map, expected titles/paths,
  skipped titles and per-action counts).
- :func:`sync_directory` — recursive directory walk.
- :func:`sync_files` — flat list of Markdown files.
"""

from sync_confluence.traversal._index import build_doc_index
from sync_confluence.traversal._state import SyncContext, SyncResult
from sync_confluence.traversal._walker import sync_directory, sync_files

__all__ = [
    "SyncContext",
    "SyncResult",
    "build_doc_index",
    "sync_directory",
    "sync_files",
]
