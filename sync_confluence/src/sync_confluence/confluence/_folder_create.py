"""Folder-creation helpers (dry-run, post-create setup, and HTTP fallback)."""

from __future__ import annotations

from typing import Optional

from atlassian import Confluence

from sync_confluence.confluence._constants import (
    _DRY_RUN_ID,
    _SOURCE_PATH_PROPERTY_KEY,
    _Actions,
    _Keys,
)
from sync_confluence.confluence._logging import log
from sync_confluence.confluence._lookup import _find_folder_by_space_cql
from sync_confluence.confluence._properties import _apply_label, _try_property_set
from sync_confluence.confluence._types import FolderUpsertRequest


def _upsert_folder_dry_run(request: FolderUpsertRequest) -> tuple[str, str]:
    if request.managed_by_label:
        log.debug(
            "[DRY-RUN] Would label folder '%s' with '%s'",
            request.title,
            request.managed_by_label,
        )
    return (_DRY_RUN_ID, _Actions.CREATED)


def _post_create_folder_setup(
    confluence: Confluence, folder_id: str, request: FolderUpsertRequest
) -> None:
    if request.managed_by_label:
        _apply_label(confluence, folder_id, request.managed_by_label)
    if request.source_path is not None:
        _try_property_set(
            confluence,
            folder_id,
            _SOURCE_PATH_PROPERTY_KEY,
            request.source_path,
            "source path",
        )


def _create_folder_via_api(confluence: Confluence, request: FolderUpsertRequest) -> str:
    folder_item = confluence.post(
        path="rest/api/content",
        data={
            "type": "folder",
            "title": request.title,
            "space": {"key": request.space_key},
            "ancestors": [{_Keys.ID: request.parent_id}],
        },
    )
    return str(folder_item[_Keys.ID])


def _is_folder_exists_error(exc) -> bool:
    """Return True if *exc* indicates a folder-already-exists conflict."""
    has_response = exc.response is not None
    return "folder exists" in str(exc).lower() or (
        has_response and exc.response.status_code in (400, 409)
    )


def _lookup_existing_folder_via_cql(
    confluence: Confluence, request: FolderUpsertRequest
) -> Optional[str]:
    try:
        return _find_folder_by_space_cql(confluence, request.space_key, request.title)
    except Exception as cql_exc:
        log.debug("CQL fallback also failed: %s", cql_exc)
        return None


def _create_folder_with_fallback(
    confluence: Confluence, request: FolderUpsertRequest
) -> tuple[str, str]:
    from requests.exceptions import HTTPError

    try:
        folder_id = _create_folder_via_api(confluence, request)
    except HTTPError as exc:
        if not _is_folder_exists_error(exc):
            raise
        log.debug(
            "Folder '%s' creation rejected (%s); attempting broader lookup",
            request.title,
            exc,
        )
        fallback_id = _lookup_existing_folder_via_cql(confluence, request)
        if fallback_id:
            log.info(
                "Found existing folder '%s' via CQL (id=%s)",
                request.title,
                fallback_id,
            )
            return (fallback_id, _Actions.UNCHANGED)
        raise
    log.info("Created folder: '%s' (id=%s)", request.title, folder_id)
    _post_create_folder_setup(confluence, folder_id, request)
    return (folder_id, _Actions.CREATED)
