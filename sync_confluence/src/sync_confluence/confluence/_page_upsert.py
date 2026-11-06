"""Public :func:`upsert_page` and its per-branch action helpers."""

from __future__ import annotations

from typing import Optional

from atlassian import Confluence

from sync_confluence.confluence._attachments import upload_attachments
from sync_confluence.confluence._constants import PageSyncAction, _Keys
from sync_confluence.confluence._logging import _suppress_atlassian_not_found, log
from sync_confluence.confluence._lookup import find_page_under_parent
from sync_confluence.confluence._page_dry_run import _upsert_page_dry_run
from sync_confluence.confluence._page_metadata import (
    _apply_page_metadata,
    _apply_page_width,
    _rename_target,
)
from sync_confluence.confluence._properties import (
    _content_hash,
    _fetch_hash_prop_value,
)
from sync_confluence.confluence._types import PageUpsertRequest


def _apply_attachments(
    confluence: Confluence, page_id: str, request: PageUpsertRequest
) -> None:
    """Upload (and reconcile) the request's attachments, if any."""
    if request.attachments:
        upload_attachments(
            confluence, page_id, request.attachments, dry_run=request.dry_run
        )


def _handle_page_rename(
    confluence: Confluence, request: PageUpsertRequest
) -> Optional[tuple[str, str]]:
    """If a rename target exists, update its body+metadata and return result."""
    rename_id = _rename_target(request)
    if rename_id is None:
        return None
    log.info(
        "Renaming page id=%s to '%s' and updating content",
        rename_id,
        request.title,
    )
    confluence.update_page(
        page_id=rename_id,
        title=request.title,
        body=request.body,
        parent_id=request.parent_id,
        representation=_Keys.STORAGE,
        minor_edit=True,
    )
    _apply_page_metadata(confluence, rename_id, request, _content_hash(request.body))
    _apply_attachments(confluence, rename_id, request)
    return (rename_id, PageSyncAction.UPDATED)


def _check_title_collision(
    confluence: Confluence, request: PageUpsertRequest
) -> Optional[tuple[None, str]]:
    """Return SKIPPED result if a same-titled page exists under a different parent."""
    with _suppress_atlassian_not_found():
        conflicting_page = confluence.get_page_by_title(
            space=request.space_key,
            title=request.title,
            expand=_Keys.VERSION,
        )
    if not conflicting_page:
        log.debug(
            "'%s' not found in space, will create under parent %s",
            request.title,
            request.parent_id,
        )
        return None
    log.warning(
        "Title collision: '%s' already exists in space (id=%s) under a "
        "different parent — skipping this file to avoid hijacking an "
        "unrelated page.",
        request.title,
        conflicting_page[_Keys.ID],
    )
    return (None, PageSyncAction.SKIPPED)


def _update_existing_page(
    confluence: Confluence, request: PageUpsertRequest, existing_id: str
) -> tuple[str, str]:
    """Hash-check then update an existing page; returns ``(id, action)``."""
    body_hash = _content_hash(request.body)
    prop_val = None
    try:
        prop_val = _fetch_hash_prop_value(confluence, existing_id)
    except Exception as exc:
        log.warning(
            "Could not fetch hash property for page id=%s (%s); will update",
            existing_id,
            exc,
        )

    if prop_val == body_hash:
        log.debug("Unchanged: '%s' (id=%s)", request.title, existing_id)
        return (existing_id, PageSyncAction.UNCHANGED)

    confluence.update_page(
        page_id=existing_id,
        title=request.title,
        body=request.body,
        parent_id=request.parent_id,
        representation=_Keys.STORAGE,
        minor_edit=True,
    )
    log.info("Updated: '%s' (id=%s)", request.title, existing_id)
    _apply_page_metadata(confluence, existing_id, request, body_hash)
    _apply_attachments(confluence, existing_id, request)
    return (existing_id, PageSyncAction.UPDATED)


def _create_new_page(
    confluence: Confluence, request: PageUpsertRequest
) -> tuple[str, str]:
    """Create a new page and apply metadata."""
    page = confluence.create_page(
        space=request.space_key,
        title=request.title,
        body=request.body,
        parent_id=request.parent_id,
        representation=_Keys.STORAGE,
    )
    page_id = str(page[_Keys.ID])
    log.info("Created: '%s' (id=%s)", request.title, page_id)
    _apply_page_metadata(
        confluence,
        page_id,
        request,
        _content_hash(request.body),
        apply_page_width=False,
    )
    _apply_page_width(confluence, page_id, request.page_width)
    _apply_attachments(confluence, page_id, request)
    return (page_id, PageSyncAction.CREATED)


def upsert_page(
    confluence: Confluence, request: PageUpsertRequest
) -> tuple[Optional[str], str]:
    """Create or update a page.  Returns ``(page_id, action)``.

    *action* is one of ``"created"``, ``"updated"``, ``"unchanged"``, or
    ``"skipped"``.  When *action* is ``"skipped"``, *page_id* is ``None`` and
    the page was not touched (a same-titled page exists in the space under a
    different parent — hijacking and re-parenting is forbidden).  In dry-run
    mode, *page_id* is ``"DRY-RUN"``.

    When ``request.managed_by_label`` is set, the label is applied to every
    created or updated page so that :func:`delete_orphans` can safely restrict
    deletions to only pages owned by this automation.

    When ``request.restrict_edits_to`` is set (an Atlassian ``accountId``),
    the page's ``update`` restriction is set to allow only that account to
    edit.  View access is left unrestricted.
    """
    if request.dry_run:
        return _upsert_page_dry_run(confluence, request)
    existing = find_page_under_parent(
        confluence, request.space_key, request.title, request.parent_id
    )
    if existing is not None:
        return _update_existing_page(confluence, request, existing[_Keys.ID])
    renamed = _handle_page_rename(confluence, request)
    if renamed is not None:
        return renamed
    collision = _check_title_collision(confluence, request)
    if collision is not None:
        return collision
    return _create_new_page(confluence, request)
