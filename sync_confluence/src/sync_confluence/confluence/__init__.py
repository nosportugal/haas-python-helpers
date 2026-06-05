"""Confluence API wrapper: pages, folders, properties, labels and cleanup.

Public surface (re-exported for backwards compatibility with the previous
single-module layout):

- :class:`PageUpsertRequest`, :class:`FolderUpsertRequest`,
  :class:`DeleteOrphansRequest` — request dataclasses.
- :func:`upsert_page`, :func:`upsert_folder` — idempotent upserts.
- :func:`build_source_path_map` — rename-detection lookup.
- :func:`delete_orphans` — bottom-up cleanup of stale pages and folders.
"""

from sync_confluence.confluence._attachments import upload_attachments
from sync_confluence.confluence._cleanup import delete_orphans
from sync_confluence.confluence._folder_upsert import upsert_folder
from sync_confluence.confluence._page_upsert import upsert_page
from sync_confluence.confluence._path_map import build_source_path_map
from sync_confluence.confluence._types import (
    DeleteOrphansRequest,
    FolderUpsertRequest,
    PageUpsertRequest,
)

__all__ = [
    "DeleteOrphansRequest",
    "FolderUpsertRequest",
    "PageUpsertRequest",
    "build_source_path_map",
    "delete_orphans",
    "upload_attachments",
    "upsert_folder",
    "upsert_page",
]
