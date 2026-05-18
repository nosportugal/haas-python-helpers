"""Top-level walker orchestration."""

from __future__ import annotations

from pathlib import Path

from sync_confluence.traversal._anchor import _anchor
from sync_confluence.traversal._md_files import _sync_md_files, _sync_one_md_file
from sync_confluence.traversal._state import SyncContext, SyncResult, log
from sync_confluence.traversal._subdirs import _create_subfolder
from sync_confluence.traversal._sync_state import _Sync, _new_state


def _recurse(state: _Sync, parent_id: str, subdir: Path, depth: int) -> None:
    sub_state = _new_state(state.ctx, allow_root_title=False)
    _walk_directory(sub_state, parent_id, subdir, depth=depth, readme_as_parent=False)
    state.recorder.merge(sub_state.recorder.outcome)


def _walk_subdirs(state: _Sync, dir_id: str, directory: Path, depth: int) -> None:
    for subdir in sorted(entry for entry in directory.iterdir() if entry.is_dir()):
        folder_id = _create_subfolder(state, dir_id, subdir, depth)
        _recurse(state, folder_id, subdir, depth + 1)


def _walk_directory(
    state: _Sync,
    parent_id: str,
    directory: Path,
    *,
    depth: int,
    readme_as_parent: bool,
) -> None:
    dir_id, child_depth = _anchor(state, parent_id, directory, depth, readme_as_parent)
    _sync_md_files(state, dir_id, directory, readme_as_parent, child_depth)
    _walk_subdirs(state, dir_id, directory, child_depth)


def _walk_files(
    state: _Sync, parent_id: str, files: list[Path], depth: int
) -> None:
    source_path_map = state.builder.build_path_map(parent_id)
    for md_file in files:
        if not md_file.is_file():
            log.warning("Skipping non-existent file: %s", md_file)
            continue
        _sync_one_md_file(state, parent_id, md_file, source_path_map, depth)


def sync_directory(
    ctx: SyncContext,
    parent_id: str,
    directory: Path,
    *,
    depth: int = 0,
    readme_as_parent: bool = True,
) -> SyncResult:
    """Recursively sync *directory* into Confluence under *parent_id*."""
    state = _new_state(ctx, allow_root_title=True)
    _walk_directory(
        state, parent_id, directory, depth=depth, readme_as_parent=readme_as_parent
    )
    return state.recorder.outcome


def sync_files(
    ctx: SyncContext, parent_id: str, files: list[Path], *, depth: int = 0
) -> SyncResult:
    """Sync a flat list of Markdown *files* as leaf pages under *parent_id*."""
    state = _new_state(ctx, allow_root_title=False)
    _walk_files(state, parent_id, files, depth)
    return state.recorder.outcome
