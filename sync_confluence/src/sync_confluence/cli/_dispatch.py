"""Build a :class:`SyncContext` and dispatch the directory or files walk."""

from __future__ import annotations

import argparse

from sync_confluence.cli._auth import _AuthInfo
from sync_confluence.cli._docs import _DocsInfo
from sync_confluence.cli._plan import _SyncPlan
from sync_confluence.cli._resolve import _SYNC_MODE_FILES
from sync_confluence.traversal import (
    SyncContext,
    SyncResult,
    sync_directory,
    sync_files,
)


def _build_sync_context(
    args: argparse.Namespace, docs: _DocsInfo, auth: _AuthInfo
) -> SyncContext:
    return SyncContext(
        confluence=auth.confluence,
        space_key=args.space,
        docs_root=docs.root,
        root_title=args.root_title,
        mermaid_macro=args.mermaid_macro,
        repo_url=auth.repo_url,
        git_ref=args.git_ref,
        dry_run=args.dry_run,
        managed_by_label=auth.managed_by_label,
        restrict_edits_to=auth.restrict_edits_to,
        page_width=args.page_width,
    )


def _dispatch_sync(
    args: argparse.Namespace, docs: _DocsInfo, auth: _AuthInfo, plan: _SyncPlan
) -> SyncResult:
    ctx = _build_sync_context(args, docs, auth)
    if docs.mode == _SYNC_MODE_FILES:
        return sync_files(ctx, plan.parent_id, docs.files, depth=plan.depth)
    return sync_directory(
        ctx,
        plan.parent_id,
        docs.root,
        depth=plan.depth,
        readme_as_parent=plan.readme_as_parent,
    )
