"""Helpers shared by the page-upsert action functions."""

from __future__ import annotations

from typing import Optional

from atlassian import Confluence

from sync_confluence.confluence._constants import (
    _APPEARANCE_DRAFT_KEY,
    _APPEARANCE_PUBLISHED_KEY,
    _HASH_PROPERTY_KEY,
    _SOURCE_PATH_PROPERTY_KEY,
)
from sync_confluence.confluence._logging import log
from sync_confluence.confluence._properties import _apply_label, _try_property_set
from sync_confluence.confluence._restrictions import _apply_edit_restriction
from sync_confluence.confluence._types import PageUpsertRequest


def _apply_page_metadata(
    confluence: Confluence,
    page_id: str,
    request: PageUpsertRequest,
    body_hash: str,
    apply_page_width: bool = True,
) -> None:
    """Apply hash + source-path properties, label, restrictions and width."""
    _try_property_set(confluence, page_id, _HASH_PROPERTY_KEY, body_hash, "hash")
    if request.source_path is not None:
        _try_property_set(
            confluence,
            page_id,
            _SOURCE_PATH_PROPERTY_KEY,
            request.source_path,
            "source path",
        )
    if request.managed_by_label:
        _apply_label(confluence, page_id, request.managed_by_label)
    if request.restrict_edits_to:
        _apply_edit_restriction(confluence, page_id, request.restrict_edits_to)
    if apply_page_width:
        _apply_page_width(confluence, page_id, request.page_width)


def _apply_page_width(
    confluence: Confluence, page_id: str, page_width: Optional[str]
) -> None:
    """Apply published+draft appearance properties when width is requested."""
    if page_width is None:
        return
    _try_property_set(
        confluence,
        page_id,
        _APPEARANCE_PUBLISHED_KEY,
        page_width,
        "appearance",
    )
    _try_property_set(
        confluence,
        page_id,
        _APPEARANCE_DRAFT_KEY,
        page_width,
        "appearance",
    )


def _log_dry_run_metadata(request: PageUpsertRequest) -> None:
    """Emit the optional [DRY-RUN] label/restriction debug lines."""
    if request.managed_by_label:
        log.debug(
            "[DRY-RUN] Would label '%s' with '%s'",
            request.title,
            request.managed_by_label,
        )
    if request.restrict_edits_to:
        log.debug(
            "[DRY-RUN] Would restrict edits on '%s' to accountId=%s",
            request.title,
            request.restrict_edits_to,
        )
    if request.page_width is not None:
        log.debug(
            "[DRY-RUN] Would set page width on '%s' to '%s'",
            request.title,
            request.page_width,
        )


def _rename_target(request: PageUpsertRequest) -> Optional[str]:
    """Return the page id to rename, if a rename should occur."""
    if request.source_path is None or not request.source_path_map:
        return None
    return request.source_path_map.get(request.source_path)
