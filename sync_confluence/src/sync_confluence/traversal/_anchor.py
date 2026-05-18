"""README-as-section-parent handling."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from sync_confluence.confluence import upsert_page
from sync_confluence.traversal._builder import _RequestBuilder
from sync_confluence.traversal._state import log
from sync_confluence.traversal._sync_state import _Sync, _maybe_log

_ICON_SECTION = "\U0001f4c1"  # 📁


def _upsert_readme(
    state: _Sync, parent_id: str, readme: Path, title: str
) -> tuple[Optional[str], str]:
    request = state.builder.build_readme_request(parent_id, readme, title)
    return upsert_page(state.ctx.confluence, request)


def _anchor_readme(
    state: _Sync, parent_id: str, readme: Path, depth: int
) -> tuple[str, int]:
    from sync_confluence.converter import derive_title

    title = derive_title(readme, state.ctx.docs_root, state.ctx.root_title)
    page_id, action = _upsert_readme(state, parent_id, readme, title)
    _maybe_log(state.ctx.dry_run, depth, _ICON_SECTION, title)
    if state.recorder.record_page(readme, title, page_id, action):
        return page_id, depth + 1  # type: ignore[return-value]
    log.debug("Anchor README %s skipped; nesting children under parent", title)
    return parent_id, depth + 1


def _anchor(
    state: _Sync,
    parent_id: str,
    directory: Path,
    depth: int,
    readme_as_parent: bool,
) -> tuple[str, int]:
    readme = directory / "README.md"
    if readme_as_parent and readme.exists():
        return _anchor_readme(state, parent_id, readme, depth)
    return parent_id, depth
