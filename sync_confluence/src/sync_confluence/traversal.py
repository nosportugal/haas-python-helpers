"""Filesystem → Confluence traversal.

The public surface is two thin wrappers, :func:`sync_directory` and
:func:`sync_files`, both of which delegate to an internal :class:`_Walker`.
The :class:`SyncContext` dataclass groups the Confluence connection and the
immutable sync configuration; the :class:`SyncResult` ``NamedTuple`` holds
the accumulated outcome.  Carrying these as attributes on the walker keeps
each method below WPS's per-function argument / local thresholds.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, Optional

from atlassian import Confluence

from sync_confluence.confluence import (
    FolderUpsertRequest,
    PageUpsertRequest,
    build_source_path_map,
    upsert_folder,
    upsert_page,
)
from sync_confluence.converter import convert_markdown, derive_title

log = logging.getLogger(__name__)

_ACTION_SKIPPED = "skipped"
_LOG_INDENT = "  "
_DRY_RUN_ID = "DRY-RUN"
_ICON_SECTION = "\U0001f4c1"  # 📁
_ICON_FILE = "\U0001f4c4"  # 📄
_ICON_FOLDER = "\U0001f4c2"  # 📂


class SyncResult(NamedTuple):
    """Collected outcome of a sync operation."""

    page_map: dict[str, str]
    expected_titles: set[str]
    expected_paths: set[str]
    skipped: list[str]
    stats: dict[str, int]


@dataclass
class SyncContext:
    """Encapsulates the Confluence connection and sync configuration."""

    confluence: Confluence
    space_key: str
    docs_root: Path
    root_title: Optional[str] = None
    mermaid_macro: Optional[str] = None
    repo_url: Optional[str] = None
    git_ref: str = "main"
    dry_run: bool = False
    managed_by_label: Optional[str] = None
    restrict_edits_to: Optional[str] = None


def _empty_sync_result() -> SyncResult:
    return SyncResult(
        page_map={},
        expected_titles=set(),
        expected_paths=set(),
        skipped=[],
        stats={"created": 0, "updated": 0, "unchanged": 0, _ACTION_SKIPPED: 0},
    )


class _Walker:
    """Stateful directory walker that accumulates a :class:`SyncResult`.

    *allow_root_title* controls whether a ``README.md`` encountered in the
    md-files loop should adopt the context's ``root_title``.  The top-level
    :func:`sync_directory` call sets it to ``True``; recursive sub-walks and
    :func:`sync_files` set it to ``False`` so nested READMEs are treated as
    regular leaves.
    """

    def __init__(self, ctx: SyncContext, *, allow_root_title: bool = True) -> None:
        self.ctx = ctx
        self.allow_root_title = allow_root_title
        self.result = _empty_sync_result()

    # ---- entry points -----------------------------------------------------

    def sync_directory(
        self,
        parent_id: str,
        directory: Path,
        *,
        depth: int = 0,
        readme_as_parent: bool = True,
    ) -> None:
        dir_page_id, child_depth = self._anchor(
            parent_id, directory, depth, readme_as_parent
        )
        self._sync_md_files(dir_page_id, directory, readme_as_parent, child_depth)
        self._sync_subdirs(dir_page_id, directory, child_depth)

    def sync_files(self, parent_id: str, files: list[Path], *, depth: int = 0) -> None:
        source_path_map = self._build_path_map(parent_id)
        for md_file in files:
            if not md_file.is_file():
                log.warning("Skipping non-existent file: %s", md_file)
                continue
            self._sync_one_md_file(parent_id, md_file, source_path_map, depth)

    # ---- anchor: optional README-as-parent --------------------------------

    def _anchor(
        self, parent_id: str, directory: Path, depth: int, readme_as_parent: bool
    ) -> tuple[str, int]:
        readme = directory / "README.md"
        if readme_as_parent and readme.exists():
            return self._anchor_readme_as_parent(parent_id, readme, depth)
        return parent_id, depth

    def _anchor_readme_as_parent(
        self, parent_id: str, readme: Path, depth: int
    ) -> tuple[str, int]:
        title = derive_title(readme, self.ctx.docs_root, self.ctx.root_title)
        page_id, action = self._upsert_readme(parent_id, readme, title)
        self._maybe_log(depth, _ICON_SECTION, title)
        if self._record_page_result(readme, title, page_id, action):
            return page_id, depth + 1
        # Skipped: caller's parent_id absorbs the children
        return parent_id, depth + 1

    def _upsert_readme(
        self, parent_id: str, readme: Path, title: str
    ) -> tuple[Optional[str], str]:
        request = PageUpsertRequest(
            space_key=self.ctx.space_key,
            parent_id=parent_id,
            title=title,
            body=self._render(readme),
            dry_run=self.ctx.dry_run,
            managed_by_label=self.ctx.managed_by_label,
            restrict_edits_to=self.ctx.restrict_edits_to,
            source_path=str(readme.relative_to(self.ctx.docs_root)),
        )
        return upsert_page(self.ctx.confluence, request)

    # ---- md-file syncing --------------------------------------------------

    def _sync_md_files(
        self,
        dir_id: str,
        directory: Path,
        readme_as_parent: bool,
        depth: int,
    ) -> None:
        md_files = self._collect_md_files(directory, readme_as_parent)
        if not md_files:
            return
        source_path_map = self._build_path_map(dir_id)
        for md_file in md_files:
            self._sync_one_md_file(dir_id, md_file, source_path_map, depth)

    def _sync_one_md_file(
        self,
        parent_id: str,
        md_file: Path,
        source_path_map: dict[str, str],
        depth: int,
    ) -> None:
        title = self._resolve_md_title(md_file)
        request = self._build_page_request(parent_id, md_file, title, source_path_map)
        page_id, action = upsert_page(self.ctx.confluence, request)
        self._maybe_log(depth, _ICON_FILE, title)
        self._record_page_result(md_file, title, page_id, action)

    def _resolve_md_title(self, md_file: Path) -> str:
        if self.allow_root_title and md_file.name == "README.md":
            return derive_title(md_file, self.ctx.docs_root, self.ctx.root_title)
        return derive_title(md_file, self.ctx.docs_root, None)

    def _build_page_request(
        self,
        parent_id: str,
        md_file: Path,
        title: str,
        source_path_map: dict[str, str],
    ) -> PageUpsertRequest:
        return PageUpsertRequest(
            space_key=self.ctx.space_key,
            parent_id=parent_id,
            title=title,
            body=self._render(md_file),
            dry_run=self.ctx.dry_run,
            managed_by_label=self.ctx.managed_by_label,
            restrict_edits_to=self.ctx.restrict_edits_to,
            source_path=str(md_file.relative_to(self.ctx.docs_root)),
            source_path_map=source_path_map,
        )

    # ---- subdirectory recursion ------------------------------------------

    def _sync_subdirs(self, dir_id: str, directory: Path, depth: int) -> None:
        subdirs = sorted(entry for entry in directory.iterdir() if entry.is_dir())
        for subdir in subdirs:
            self._sync_subdir(dir_id, subdir, depth)

    def _sync_subdir(self, parent_id: str, subdir: Path, depth: int) -> None:
        folder_title = subdir.name.replace("-", " ").title()
        folder_id = self._upsert_subfolder(parent_id, subdir, folder_title)
        self.result.expected_titles.add(folder_title)
        self.result.expected_paths.add(str(subdir.relative_to(self.ctx.docs_root)))
        self._maybe_log(depth, _ICON_FOLDER, folder_title)
        self._recurse(folder_id, subdir, depth + 1)

    def _upsert_subfolder(self, parent_id: str, subdir: Path, folder_title: str) -> str:
        request = FolderUpsertRequest(
            space_key=self.ctx.space_key,
            parent_id=parent_id,
            title=folder_title,
            dry_run=self.ctx.dry_run,
            managed_by_label=self.ctx.managed_by_label,
            source_path=str(subdir.relative_to(self.ctx.docs_root)),
        )
        folder_id, _ = upsert_folder(self.ctx.confluence, request)
        return folder_id

    def _recurse(self, parent_id: str, subdir: Path, depth: int) -> None:
        # Nested walks: README.md is just a regular file (root_title doesn't
        # cascade into subdirectories).
        sub = _Walker(self.ctx, allow_root_title=False)
        sub.sync_directory(parent_id, subdir, depth=depth, readme_as_parent=False)
        self._merge(sub.result)

    # ---- result bookkeeping ----------------------------------------------

    def _record_page_result(
        self, source_file: Path, title: str, page_id: Optional[str], action: str
    ) -> bool:
        """Update self.result; return True on success, False when skipped."""
        if action == _ACTION_SKIPPED:
            self.result.skipped.append(title)
            self.result.stats[_ACTION_SKIPPED] += 1
            return False
        self.result.page_map[str(source_file)] = page_id  # type: ignore[assignment]
        self.result.expected_titles.add(title)
        self.result.expected_paths.add(str(source_file.relative_to(self.ctx.docs_root)))
        self.result.stats[action] += 1
        return True

    def _merge(self, other: SyncResult) -> None:
        self.result.page_map.update(other.page_map)
        self.result.expected_titles.update(other.expected_titles)
        self.result.expected_paths.update(other.expected_paths)
        self.result.skipped.extend(other.skipped)
        for stat_key in self.result.stats:
            self.result.stats[stat_key] += other.stats[stat_key]

    # ---- helpers ----------------------------------------------------------

    def _build_path_map(self, page_id: str) -> dict[str, str]:
        if self.ctx.dry_run or page_id == _DRY_RUN_ID:
            return {}
        return build_source_path_map(self.ctx.confluence, page_id)

    def _render(self, md_file: Path) -> str:
        return convert_markdown(
            md_file.read_text(encoding="utf-8"),
            mermaid_macro=self.ctx.mermaid_macro,
            repo_url=self.ctx.repo_url,
            git_ref=self.ctx.git_ref,
            current_file=md_file,
        )

    def _maybe_log(self, depth: int, icon: str, title: str) -> None:
        if self.ctx.dry_run:
            log.info("%s%s %s", _LOG_INDENT * depth, icon, title)

    @staticmethod
    def _collect_md_files(directory: Path, readme_as_parent: bool) -> list[Path]:
        if readme_as_parent:
            return sorted(
                md_path
                for md_path in directory.glob("*.md")
                if md_path.name != "README.md"
            )
        return sorted(directory.glob("*.md"))


# ---- public module-level API ---------------------------------------------


def sync_directory(
    ctx: SyncContext,
    parent_id: str,
    directory: Path,
    *,
    depth: int = 0,
    readme_as_parent: bool = True,
) -> SyncResult:
    """Recursively sync *directory* into Confluence under *parent_id*.

    When *readme_as_parent* is ``True`` (the default), the top-level
    ``README.md`` becomes the section parent page and other files attach
    beneath it.  Subdirectories always map to Confluence Folders.

    Returns a :class:`SyncResult` with page map, expected titles/paths, the
    list of titles skipped due to space-wide title collisions, and per-action
    counts.
    """
    walker = _Walker(ctx, allow_root_title=True)
    walker.sync_directory(
        parent_id, directory, depth=depth, readme_as_parent=readme_as_parent
    )
    return walker.result


def sync_files(
    ctx: SyncContext, parent_id: str, files: list[Path], *, depth: int = 0
) -> SyncResult:
    """Sync a flat list of Markdown *files* as leaf pages under *parent_id*.

    Non-existent files are skipped with a warning.  README.md is treated as
    a regular file (the context's ``root_title`` is **not** applied).
    Returns a :class:`SyncResult`.
    """
    walker = _Walker(ctx, allow_root_title=False)
    walker.sync_files(parent_id, files, depth=depth)
    return walker.result
