"""Build a :class:`SyncContext` and dispatch the directory or files walk."""

from __future__ import annotations

import argparse
import logging
import shlex
from pathlib import Path

from sync_confluence.cli._auth import _AuthInfo
from sync_confluence.cli._docs import _DocsInfo
from sync_confluence.cli._plan import _SyncPlan
from sync_confluence.cli._resolve import _SYNC_MODE_FILES
from sync_confluence.traversal import (
    SyncContext,
    SyncResult,
    build_doc_index,
    sync_directory,
    sync_files,
)
from sync_confluence.traversal._diagrams import find_mmdc, make_mermaid_renderer

log = logging.getLogger(__name__)


def _collect_index_files(docs: _DocsInfo) -> list[Path]:
    if docs.mode == _SYNC_MODE_FILES:
        return docs.files
    return sorted(docs.root.rglob("*.md"))


def _build_sync_context(
    args: argparse.Namespace, docs: _DocsInfo, auth: _AuthInfo
) -> SyncContext:
    render = getattr(args, "render_mermaid", False) and not args.dry_run
    mmdc = find_mmdc(getattr(args, "mmdc_path", None)) if render else None
    if render and mmdc is None:
        log.warning("Mermaid rendering requested but mmdc not found; falling back")
    mmdc_args_str = getattr(args, "mmdc_args", None)
    extra_args = tuple(shlex.split(mmdc_args_str)) if mmdc_args_str else ()
    renderer = make_mermaid_renderer(mmdc, extra_args) if mmdc else None
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
        doc_index=build_doc_index(
            docs.root, args.root_title, _collect_index_files(docs)
        ),
        generated_by="" if args.no_generated_by else args.generated_by,
        mermaid_renderer=renderer,
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
