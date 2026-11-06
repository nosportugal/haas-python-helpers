"""Confluence API wrapper: pages, folders, properties, labels and cleanup.

Public surface (re-exported for backwards compatibility with the previous
single-module layout):

- :class:`PageUpsertRequest`, :class:`FolderUpsertRequest`,
  :class:`DeleteOrphansRequest` — request dataclasses.
- :func:`upsert_page`, :func:`upsert_folder` — idempotent upserts.
- :func:`build_source_path_map` — rename-detection lookup.
- :func:`delete_orphans` — bottom-up cleanup of stale pages and folders.
- :data:`DRY_RUN_PAGE_ID`, :class:`PageSyncAction` — dry-run placeholder page id
  and upsert action values.
- :func:`find_page_under_parent`, :func:`find_folder_under_parent` — lookups.
"""

from sync_confluence.confluence._attachments import upload_attachments
from sync_confluence.confluence._cleanup import delete_orphans
from sync_confluence.confluence._constants import DRY_RUN_PAGE_ID, PageSyncAction
from sync_confluence.confluence._folder_upsert import upsert_folder
from sync_confluence.confluence._lookup import (
    find_folder_under_parent,
    find_page_under_parent,
)
from sync_confluence.confluence._page_upsert import upsert_page
from sync_confluence.confluence._path_map import build_source_path_map
from sync_confluence.confluence._types import (
    DeleteOrphansRequest,
    FolderUpsertRequest,
    PageUpsertRequest,
)

__all__ = [
    "DRY_RUN_PAGE_ID",
    "DeleteOrphansRequest",
    "FolderUpsertRequest",
    "PageSyncAction",
    "PageUpsertRequest",
    "build_source_path_map",
    "delete_orphans",
    "find_folder_under_parent",
    "find_page_under_parent",
    "upload_attachments",
    "upsert_folder",
    "upsert_page",
]
