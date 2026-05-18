"""Public :func:`upsert_folder` and the refresh helper for existing folders."""

from __future__ import annotations

from atlassian import Confluence

from sync_confluence.confluence._constants import (
    _Actions,
    _Keys,
    _SOURCE_PATH_PROPERTY_KEY,
)
from sync_confluence.confluence._folder_create import (
    _create_folder_with_fallback,
    _upsert_folder_dry_run,
)
from sync_confluence.confluence._logging import log
from sync_confluence.confluence._lookup import _find_folder_under_parent
from sync_confluence.confluence._properties import _apply_label, _try_property_set
from sync_confluence.confluence._types import FolderUpsertRequest


def _refresh_existing_folder(
    confluence: Confluence, request: FolderUpsertRequest, existing_id: str
) -> tuple[str, str]:
    log.debug("Unchanged folder: '%s' (id=%s)", request.title, existing_id)
    # Re-apply label so it is self-healing if it was ever missing.
    if request.managed_by_label:
        _apply_label(confluence, existing_id, request.managed_by_label)
    if request.source_path is not None:
        _try_property_set(
            confluence,
            existing_id,
            _SOURCE_PATH_PROPERTY_KEY,
            request.source_path,
            "source path",
        )
    return (existing_id, _Actions.UNCHANGED)


def upsert_folder(
    confluence: Confluence, request: FolderUpsertRequest
) -> tuple[str, str]:
    """Create or find a Confluence Folder.  Returns ``(folder_id, action)``.

    *action* is one of ``"created"`` or ``"unchanged"``.  In dry-run mode,
    *folder_id* is ``"DRY-RUN"``.  Folders have no editable body content,
    so no edit restriction is applied.  ``request.managed_by_label`` is
    attached on creation so that ``delete_orphans`` can identify and clean
    up stale folders.
    """
    if request.dry_run:
        return _upsert_folder_dry_run(request)
    existing = _find_folder_under_parent(
        confluence, request.space_key, request.title, request.parent_id
    )
    if existing:
        return _refresh_existing_folder(confluence, request, existing[_Keys.ID])
    return _create_folder_with_fallback(confluence, request)
