"""Determine the parent page, depth, and README handling for the walk."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from typing import Optional

from atlassian import Confluence

from sync_confluence.confluence import (
    DRY_RUN_PAGE_ID,
    FolderUpsertRequest,
    find_folder_under_parent,
    find_page_under_parent,
    upsert_folder,
)

log = logging.getLogger(__name__)


@dataclass
class _SyncPlan:
    """Where and how to walk the docs tree."""

    parent_id: str
    readme_as_parent: bool
    depth: int


def _find_or_create_root_parent(
    confluence: Confluence, args: argparse.Namespace, managed_by_label: Optional[str]
) -> str:
    existing = find_folder_under_parent(
        confluence, args.space, args.root_parent, args.parent_id
    )
    if existing is None:
        existing = find_page_under_parent(
            confluence, args.space, args.root_parent, args.parent_id
        )
    if existing:
        log.info("Found root parent '%s' (id=%s)", args.root_parent, existing["id"])
        return existing["id"]
    folder_id, _ = upsert_folder(
        confluence,
        FolderUpsertRequest(
            space_key=args.space,
            parent_id=args.parent_id,
            title=args.root_parent,
            dry_run=False,
            managed_by_label=managed_by_label,
        ),
    )
    log.info("Created root parent '%s' (id=%s)", args.root_parent, folder_id)
    return folder_id


def _resolve_root_parent(
    confluence: Confluence, args: argparse.Namespace, managed_by_label: Optional[str]
) -> str:
    log.info(
        "Searching for root parent '%s' under parent %s",
        args.root_parent,
        args.parent_id,
    )
    if args.dry_run:
        log.info(
            "Would find or create root parent '%s' under parent %s",
            args.root_parent,
            args.parent_id,
        )
        return DRY_RUN_PAGE_ID
    return _find_or_create_root_parent(confluence, args, managed_by_label)


def _resolve_sync_plan(
    confluence: Confluence, args: argparse.Namespace, managed_by_label: Optional[str]
) -> _SyncPlan:
    """Determine the parent page, depth, and README handling for the walk."""
    if args.no_root:
        return _SyncPlan(parent_id=args.parent_id, readme_as_parent=False, depth=0)
    if not args.root_parent:
        return _SyncPlan(parent_id=args.parent_id, readme_as_parent=True, depth=0)
    parent_id = _resolve_root_parent(confluence, args, managed_by_label)
    return _SyncPlan(parent_id=parent_id, readme_as_parent=False, depth=1)
