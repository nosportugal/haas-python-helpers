"""Push test cases to Confluence: one folder per vendor, one page per test."""

from __future__ import annotations

import logging

from atlassian import Confluence

from sync_confluence.confluence import (
    FolderUpsertRequest,
    PageUpsertRequest,
    build_source_path_map,
    upsert_folder,
    upsert_page,
)
from sync_confluence.confluence._constants import _DRY_RUN_ID, _Actions, _Keys
from sync_confluence.confluence._lookup import _find_folder_under_parent
from sync_confluence.testspec._labels import page_labels
from sync_confluence.testspec._model import TestCase, TestSpecSyncConfig
from sync_confluence.testspec._render import render_test_case
from sync_confluence.traversal import SyncResult
from sync_confluence.traversal._state import _new_sync_result

log = logging.getLogger(__name__)

_SOURCE_PREFIX = "testspec"


def _sort_key(case: TestCase) -> tuple[str, tuple[int, ...]]:
    id_parts = tuple(int(part) for part in case.test_id.split("."))
    return (case.vendor, id_parts)


def _group_by_vendor(cases: list[TestCase]) -> dict[str, list[TestCase]]:
    groups: dict[str, list[TestCase]] = {}
    for case in sorted(cases, key=_sort_key):
        groups.setdefault(case.vendor, []).append(case)
    return groups


def _upsert_vendor_folder(
    confluence: Confluence, vendor: str, config: TestSpecSyncConfig
) -> str:
    if config.dry_run:
        # upsert_folder returns a placeholder id in dry-run, which would make
        # every existing page look new; use the real folder when there is one.
        existing = _find_folder_under_parent(
            confluence, config.space_key, vendor, config.parent_id
        )
        if existing:
            return existing[_Keys.ID]
    folder_id, _ = upsert_folder(
        confluence,
        FolderUpsertRequest(
            space_key=config.space_key,
            parent_id=config.parent_id,
            title=vendor,
            dry_run=config.dry_run,
            managed_by_label=config.managed_by_label,
            source_path=f"{_SOURCE_PREFIX}/{vendor}",
        ),
    )
    return folder_id


def _page_request(
    case: TestCase,
    folder_id: str,
    path_map: dict[str, str],
    config: TestSpecSyncConfig,
) -> PageUpsertRequest:
    return PageUpsertRequest(
        space_key=config.space_key,
        parent_id=folder_id,
        title=case.title,
        body=render_test_case(case, config.source_file, config.generated_by),
        dry_run=config.dry_run,
        managed_by_label=config.managed_by_label,
        restrict_edits_to=config.restrict_edits_to,
        source_path=f"{_SOURCE_PREFIX}/{case.vendor}/{case.test_id}",
        source_path_map=path_map,
        page_width=config.page_width,
        labels=page_labels(case),
    )


def _record(outcome: SyncResult, request: PageUpsertRequest, action: str) -> None:
    log.info("%s: %s", action, request.title)
    outcome.stats[action] += 1
    if action == _Actions.SKIPPED:
        outcome.skipped.append(request.title)
        return
    outcome.expected_titles.add(request.title)
    outcome.expected_paths.add(str(request.source_path))


def _sync_vendor(
    confluence: Confluence,
    cases: list[TestCase],
    config: TestSpecSyncConfig,
    outcome: SyncResult,
) -> None:
    vendor = cases[0].vendor
    folder_id = _upsert_vendor_folder(confluence, vendor, config)
    outcome.expected_titles.add(vendor)
    outcome.expected_paths.add(f"{_SOURCE_PREFIX}/{vendor}")
    path_map = {}
    if folder_id != _DRY_RUN_ID:
        path_map = build_source_path_map(confluence, folder_id)
    for case in cases:
        request = _page_request(case, folder_id, path_map, config)
        _record(outcome, request, upsert_page(confluence, request)[1])


def sync_test_cases(
    confluence: Confluence, cases: list[TestCase], config: TestSpecSyncConfig
) -> SyncResult:
    """Upsert a folder per vendor and a page per test case under the parent."""
    outcome = _new_sync_result()
    for vendor_cases in _group_by_vendor(cases).values():
        _sync_vendor(confluence, vendor_cases, config, outcome)
    return outcome
