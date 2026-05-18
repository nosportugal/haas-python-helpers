"""Resolve docs and log the sync target."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

from sync_confluence.cli._resolve import (
    _DocsInfo,
    _SYNC_MODE_FILES,
    _resolve_docs_root,
)

log = logging.getLogger(__name__)

_DRY_RUN_ID = "DRY-RUN"


def _log_sync_target(
    sync_mode: str, docs_files: list[Path], docs_root: Path, dry_run: bool
) -> None:
    mode_label = _DRY_RUN_ID if dry_run else "LIVE"
    if sync_mode == _SYNC_MODE_FILES:
        log.info("Syncing %d file(s)  |  Mode: %s", len(docs_files), mode_label)
    else:
        log.info("Docs dir: %s  |  Mode: %s", docs_root, mode_label)


def _resolve_docs(args: argparse.Namespace) -> Optional[_DocsInfo]:
    """Resolve docs location, log the sync target, or return ``None`` on error."""
    docs_root, sync_mode, docs_files = _resolve_docs_root(args)
    if docs_root is None:
        return None
    _log_sync_target(sync_mode, docs_files, docs_root, args.dry_run)
    return _DocsInfo(root=docs_root, mode=sync_mode, files=docs_files)
