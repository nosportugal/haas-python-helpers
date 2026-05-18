"""Apply edit restrictions to Confluence pages."""

from __future__ import annotations

from atlassian import Confluence

from sync_confluence.confluence._logging import log


def _request_edit_restriction(
    confluence: Confluence, page_id: str, account_id: str
) -> None:
    """Execute the PUT to set edit restrictions; raises on HTTP error."""
    api_response = confluence.request(
        method="PUT",
        path=f"rest/api/content/{page_id}/restriction/byOperation/update/user",
        params={"accountId": account_id},
        advanced_mode=True,
    )
    api_response.raise_for_status()
    log.debug("Set edit restriction on page id=%s to accountId=%s", page_id, account_id)


def _apply_edit_restriction(
    confluence: Confluence, page_id: str, account_id: str
) -> None:
    """Restrict edit access on the page to the given Atlassian accountId."""
    try:
        _request_edit_restriction(confluence, page_id, account_id)
    except Exception as exc:
        log.warning(
            "Could not set edit restriction on page id=%s: %s",
            page_id,
            exc,
        )
