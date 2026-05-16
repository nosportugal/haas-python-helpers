from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from atlassian import Confluence
from .confluence import build_source_path_map, upsert_folder, upsert_page
from .converter import convert_markdown, derive_title

log = logging.getLogger(__name__)


def sync_directory(
    confluence: Confluence,
    space_key: str,
    parent_id: str,
    directory: Path,
    docs_root: Path,
    *,
    root_title: Optional[str] = None,
    mermaid_macro: Optional[str] = None,
    repo_url: Optional[str] = None,
    git_ref: str = "main",
    dry_run: bool = False,
    depth: int = 0,
    readme_as_parent: bool = True,
    managed_by_label: Optional[str] = None,
    restrict_edits_to: Optional[str] = None,
) -> tuple[dict[str, str], set[str], set[str], list[str], dict[str, int]]:
    """Recursively sync a directory to Confluence.

    Returns ``(page_map, expected_titles, expected_paths, skipped, stats)``
    where *page_map* maps file paths to page IDs, *expected_titles* is the set
    of all page titles that should exist, *expected_paths* is the set of
    docs-root-relative source paths for all synced files and directories,
    *skipped* is the list of titles that were not synced due to a title
    collision with an unrelated page in the space, and *stats* is a dict with
    counts for ``"created"``, ``"updated"``, ``"unchanged"``, and
    ``"skipped"`` actions.

    When *readme_as_parent* is ``False``, README.md is treated as a regular
    child page and all files are synced directly under *parent_id*.

    Every subdirectory always maps to a Confluence Folder; README.md inside
    it becomes a regular child page.
    """
    page_map: dict[str, str] = {}
    expected_titles: set[str] = set()
    expected_paths: set[str] = set()
    skipped: list[str] = []
    stats: dict[str, int] = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0}

    readme = directory / "README.md"

    if readme_as_parent and readme.exists():
        # README.md becomes the section parent page
        title = derive_title(readme, docs_root, root_title)
        body = convert_markdown(
            readme.read_text(encoding="utf-8"),
            mermaid_macro=mermaid_macro,
            repo_url=repo_url,
            git_ref=git_ref,
            docs_dir=str(docs_root),
            current_file=readme,
        )
        dir_page_id, action = upsert_page(
            confluence,
            space_key,
            parent_id,
            title,
            body,
            dry_run,
            managed_by_label,
            restrict_edits_to,
            source_path=str(readme.relative_to(docs_root)),
        )
        if action == "skipped":
            skipped.append(title)
            stats["skipped"] += 1
            # Cannot build a parent page — fall back to syncing children
            # directly under the caller's parent_id.
            dir_page_id = parent_id
        else:
            page_map[str(readme)] = dir_page_id
            expected_titles.add(title)
            expected_paths.add(str(readme.relative_to(docs_root)))
            stats[action] += 1
        if dry_run:
            log.info("%s📁 %s", "  " * depth, title)
        file_depth = depth + 1
        child_depth = depth + 1
    else:
        dir_page_id = parent_id
        file_depth = depth
        child_depth = depth

    # Build source-path → page-id map for rename detection.
    # Only populated in real (non-dry-run) mode and when the parent ID is known.
    # In dry-run mode dir_page_id may be "DRY-RUN" for newly-created parents,
    # so we skip the lookup in that case.
    source_path_map: dict[str, str] = {}
    if not dry_run and dir_page_id not in ("DRY-RUN",):
        source_path_map = build_source_path_map(confluence, dir_page_id)

    # Collect .md files: exclude README.md when it is the section parent
    if readme_as_parent:
        md_files = sorted(f for f in directory.glob("*.md") if f.name != "README.md")
    else:
        md_files = sorted(directory.glob("*.md"))

    for md_file in md_files:
        title = derive_title(
            md_file,
            docs_root,
            root_title if md_file.name == "README.md" else None,
        )
        body = convert_markdown(
            md_file.read_text(encoding="utf-8"),
            mermaid_macro=mermaid_macro,
            repo_url=repo_url,
            git_ref=git_ref,
            docs_dir=str(docs_root),
            current_file=md_file,
        )
        page_id, action = upsert_page(
            confluence,
            space_key,
            dir_page_id,
            title,
            body,
            dry_run,
            managed_by_label,
            restrict_edits_to,
            source_path=str(md_file.relative_to(docs_root)),
            source_path_map=source_path_map,
        )
        if action == "skipped":
            skipped.append(title)
            stats["skipped"] += 1
        else:
            page_map[str(md_file)] = page_id
            expected_titles.add(title)
            expected_paths.add(str(md_file.relative_to(docs_root)))
            stats[action] += 1
        if dry_run:
            log.info("%s📄 %s", "  " * file_depth, title)

    # Recurse into subdirectories alphabetically
    subdirs = sorted(d for d in directory.iterdir() if d.is_dir())
    for subdir in subdirs:
        folder_title = subdir.name.replace("-", " ").title()
        folder_id, _faction = upsert_folder(
            confluence,
            space_key,
            dir_page_id,
            folder_title,
            dry_run,
            managed_by_label,
            source_path=str(subdir.relative_to(docs_root)),
        )
        expected_titles.add(folder_title)
        expected_paths.add(str(subdir.relative_to(docs_root)))
        if dry_run:
            log.info("%s📂 %s", "  " * child_depth, folder_title)
        sub_map, sub_titles, sub_paths, sub_skipped, sub_stats = sync_directory(
            confluence,
            space_key,
            folder_id,
            subdir,
            docs_root,
            mermaid_macro=mermaid_macro,
            repo_url=repo_url,
            git_ref=git_ref,
            dry_run=dry_run,
            depth=child_depth + 1,
            readme_as_parent=False,
            managed_by_label=managed_by_label,
            restrict_edits_to=restrict_edits_to,
        )
        page_map.update(sub_map)
        expected_titles.update(sub_titles)
        expected_paths.update(sub_paths)
        skipped.extend(sub_skipped)
        for k in stats:
            stats[k] += sub_stats[k]

    return page_map, expected_titles, expected_paths, skipped, stats


def sync_files(
    confluence: Confluence,
    space_key: str,
    parent_id: str,
    files: list[Path],
    docs_root: Path,
    *,
    mermaid_macro: Optional[str] = None,
    repo_url: Optional[str] = None,
    git_ref: str = "main",
    dry_run: bool = False,
    depth: int = 0,
    managed_by_label: Optional[str] = None,
    restrict_edits_to: Optional[str] = None,
) -> tuple[dict[str, str], set[str], set[str], list[str], dict[str, int]]:
    """Sync a flat list of Markdown files as leaf pages under *parent_id*.

    Each file is synced as a standalone leaf page directly under *parent_id*;
    no folder structure is created.  Non-existent files are skipped with a
    warning.

    Returns ``(page_map, expected_titles, expected_paths, skipped, stats)``
    where *skipped* is the list of titles not synced due to a space-wide title
    collision and *stats* is a dict with counts for ``"created"``,
    ``"updated"``, ``"unchanged"``, and ``"skipped"`` actions.
    """
    page_map: dict[str, str] = {}
    expected_titles: set[str] = set()
    expected_paths: set[str] = set()
    skipped: list[str] = []
    stats: dict[str, int] = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0}

    for md_file in files:
        if not md_file.is_file():
            log.warning("Skipping non-existent file: %s", md_file)
            continue

        title = derive_title(md_file, docs_root, None)
        body = convert_markdown(
            md_file.read_text(encoding="utf-8"),
            mermaid_macro=mermaid_macro,
            repo_url=repo_url,
            git_ref=git_ref,
            docs_dir=str(docs_root),
            current_file=md_file,
        )
    source_path_map: dict[str, str] = {}
    if not dry_run and parent_id not in ("DRY-RUN",):
        source_path_map = build_source_path_map(confluence, parent_id)

    for md_file in files:
        if not md_file.is_file():
            log.warning("Skipping non-existent file: %s", md_file)
            continue

        title = derive_title(md_file, docs_root, None)
        body = convert_markdown(
            md_file.read_text(encoding="utf-8"),
            mermaid_macro=mermaid_macro,
            repo_url=repo_url,
            git_ref=git_ref,
            docs_dir=str(docs_root),
            current_file=md_file,
        )
        page_id, action = upsert_page(
            confluence,
            space_key,
            parent_id,
            title,
            body,
            dry_run,
            managed_by_label,
            restrict_edits_to,
            source_path=str(md_file.relative_to(docs_root)),
            source_path_map=source_path_map,
        )
        if action == "skipped":
            skipped.append(title)
            stats["skipped"] += 1
        else:
            page_map[str(md_file)] = page_id
            expected_titles.add(title)
            expected_paths.add(str(md_file.relative_to(docs_root)))
            stats[action] += 1
        if dry_run:
            log.info("%s📄 %s", "  " * depth, title)

    return page_map, expected_titles, expected_paths, skipped, stats
