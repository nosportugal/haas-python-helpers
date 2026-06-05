"""Sync ``.md`` files (excluding the anchor README) under a parent page."""

from __future__ import annotations

from pathlib import Path

from sync_confluence.confluence import upsert_page
from sync_confluence.converter import ConversionError
from sync_confluence.traversal._builder import _collect_md_files
from sync_confluence.traversal._state import log
from sync_confluence.traversal._sync_state import _maybe_log, _Sync

_ICON_FILE = "\U0001f4c4"  # 📄


def _sync_one_md_file(
    state: _Sync,
    parent_id: str,
    md_file: Path,
    source_path_map: dict[str, str],
    depth: int,
) -> None:
    title = state.builder.resolve_md_title(md_file)
    try:
        request = state.builder.build_page_request(
            parent_id, md_file, title, source_path_map
        )
    except ConversionError as exc:
        log.warning("Skipping %s: conversion failed (%s)", md_file, exc)
        return
    page_id, action = upsert_page(state.ctx.confluence, request)
    _maybe_log(state.ctx.dry_run, depth, _ICON_FILE, title)
    state.recorder.record_page(md_file, title, page_id, action)


def _sync_md_files(
    state: _Sync,
    dir_id: str,
    directory: Path,
    readme_as_parent: bool,
    depth: int,
) -> None:
    md_files = _collect_md_files(directory, readme_as_parent)
    if not md_files:
        return
    source_path_map = state.builder.build_path_map(dir_id)
    for md_file in md_files:
        _sync_one_md_file(state, dir_id, md_file, source_path_map, depth)
