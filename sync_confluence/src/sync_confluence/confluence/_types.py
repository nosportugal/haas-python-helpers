"""Dataclasses describing the inputs to public upsert / cleanup operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sync_confluence.converter import Attachment


@dataclass
class PageUpsertRequest:
    """Arguments for :func:`sync_confluence.confluence.upsert_page`."""

    space_key: str
    parent_id: str
    title: str
    body: str
    dry_run: bool = False
    managed_by_label: Optional[str] = None
    restrict_edits_to: Optional[str] = None
    source_path: Optional[str] = None
    source_path_map: Optional[dict[str, str]] = None
    page_width: Optional[str] = None
    attachments: list[Attachment] = field(default_factory=list)


@dataclass
class FolderUpsertRequest:
    """Arguments for :func:`sync_confluence.confluence.upsert_folder`."""

    space_key: str
    parent_id: str
    title: str
    dry_run: bool = False
    managed_by_label: Optional[str] = None
    source_path: Optional[str] = None


@dataclass
class DeleteOrphansRequest:
    """Arguments for :func:`sync_confluence.confluence.delete_orphans`."""

    root_page_id: str
    expected_titles: set[str]
    dry_run: bool = False
    managed_by_label: Optional[str] = None
    expected_paths: Optional[set[str]] = None
