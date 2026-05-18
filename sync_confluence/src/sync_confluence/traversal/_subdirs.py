"""Folder creation for subdirectories during a directory walk."""

from __future__ import annotations

from pathlib import Path

from sync_confluence.confluence import upsert_folder
from sync_confluence.traversal._sync_state import _maybe_log, _Sync

_ICON_FOLDER = "\U0001f4c2"  # 📂


def _create_subfolder(state: _Sync, parent_id: str, subdir: Path, depth: int) -> str:
    folder_title = subdir.name.replace("-", " ").title()
    request = state.builder.build_folder_request(parent_id, subdir, folder_title)
    folder_id, _ = upsert_folder(state.ctx.confluence, request)
    state.recorder.record_folder(
        folder_title, str(subdir.relative_to(state.ctx.docs_root))
    )
    _maybe_log(state.ctx.dry_run, depth, _ICON_FOLDER, folder_title)
    return folder_id
