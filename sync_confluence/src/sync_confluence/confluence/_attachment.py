"""Confluence attachment upsert — create or update a page attachment."""

from __future__ import annotations

import logging
from typing import Optional

from atlassian import Confluence

log = logging.getLogger(__name__)

_DRY_RUN_ID = "DRY-RUN"


def upsert_attachment(  # noqa: WPS211 — six args matches the Confluence API shape
    confluence: Confluence,
    page_id: str,
    filename: str,
    raw_bytes: bytes,
    content_type: str,
    *,
    dry_run: bool = False,
) -> str:
    """Upload *data* as an attachment named *filename* on *page_id*.

    If an attachment with the same filename already exists it is updated
    in-place.  Returns the attachment ID (or ``"DRY-RUN"`` in dry-run mode).
    """
    if dry_run:
        log.info("[DRY-RUN] Would upload attachment %s to page %s", filename, page_id)
        return _DRY_RUN_ID

    existing_id = _find_attachment_id(confluence, page_id, filename)
    if existing_id:
        return _update_attachment(
            confluence, page_id, existing_id, filename, raw_bytes, content_type
        )
    return _create_attachment(confluence, page_id, filename, raw_bytes, content_type)


def _find_attachment_id(
    confluence: Confluence, page_id: str, filename: str
) -> Optional[str]:
    """Return the attachment ID for *filename* on *page_id*, or ``None``."""
    # Any: atlassian-python-api client has no type stubs
    api_resp = confluence.get_attachments_from_content(  # type: ignore[attr-defined]
        page_id, filename=filename, limit=1
    )
    att_items = api_resp.get("results", [])
    if att_items:
        return str(att_items[0]["id"])
    return None


def _create_attachment(
    confluence: Confluence,
    page_id: str,
    filename: str,
    raw_bytes: bytes,
    content_type: str,
) -> str:
    """POST a new attachment; return its ID."""
    # Any: atlassian-python-api returns untyped dicts
    api_resp = confluence.attach_content(  # type: ignore[attr-defined]
        content=raw_bytes,
        name=filename,
        content_type=content_type,
        page_id=page_id,
    )
    attachment_id = str(api_resp["results"][0]["id"])
    log.debug(
        "Created attachment %s (id=%s) on page %s", filename, attachment_id, page_id
    )
    return attachment_id


def _update_attachment(  # noqa: WPS211 — six args matches the Confluence API shape
    confluence: Confluence,
    page_id: str,
    attachment_id: str,
    filename: str,
    raw_bytes: bytes,
    content_type: str,
) -> str:
    """PUT updated content for an existing attachment; return its ID."""
    confluence.update_attachment(  # type: ignore[attr-defined]
        page_id=page_id,
        attachment_id=attachment_id,
        content=raw_bytes,
        name=filename,
        content_type=content_type,
    )
    log.debug(
        "Updated attachment %s (id=%s) on page %s", filename, attachment_id, page_id
    )
    return attachment_id
