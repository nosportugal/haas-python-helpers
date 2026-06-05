"""Upload page attachments and reconcile ones no longer referenced."""

from __future__ import annotations

from atlassian import Confluence

from sync_confluence.confluence._constants import _Keys
from sync_confluence.confluence._logging import log
from sync_confluence.converter import Attachment


def _upload_one(confluence: Confluence, page_id: str, attachment: Attachment) -> None:
    try:
        confluence.attach_file(
            str(attachment.path), name=attachment.name, page_id=page_id
        )
    except Exception as exc:
        log.warning(
            "Could not upload attachment '%s' to page id=%s: %s",
            attachment.name,
            page_id,
            exc,
        )


def _delete_unreferenced(
    confluence: Confluence, page_id: str, wanted: set[str]
) -> None:
    try:
        existing = confluence.get_attachments_from_content(page_id) or {}
    except Exception as exc:
        log.warning("Could not list attachments for page id=%s: %s", page_id, exc)
        return
    for attachment in existing.get(_Keys.RESULTS, []):
        title = attachment.get(_Keys.TITLE)
        if title and title not in wanted:
            _delete_one(confluence, page_id, title)


def _delete_one(confluence: Confluence, page_id: str, title: str) -> None:
    try:
        confluence.delete_attachment(page_id, title)
    except Exception as exc:
        log.warning(
            "Could not delete attachment '%s' on page id=%s: %s", title, page_id, exc
        )
        return
    log.info("Deleted unreferenced attachment '%s' (page id=%s)", title, page_id)


def upload_attachments(
    confluence: Confluence,
    page_id: str,
    attachments: list[Attachment],
    *,
    dry_run: bool = False,
) -> None:
    """Upload *attachments* to *page_id*, then delete unreferenced ones.

    In dry-run mode no API calls are made.  Failures are logged but never
    raised, so a single bad attachment does not abort the sync.
    """
    if dry_run:
        for pending in attachments:
            log.debug("[DRY-RUN] Would upload attachment '%s'", pending.name)
        return
    for attachment in attachments:
        _upload_one(confluence, page_id, attachment)
    wanted = {att.name for att in attachments}
    _delete_unreferenced(confluence, page_id, wanted)
