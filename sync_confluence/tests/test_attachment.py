from __future__ import annotations

from unittest.mock import MagicMock

from sync_confluence.confluence._attachment import upsert_attachment

_PAGE_ID = "page-1"


class TestUpsertAttachment:
    """Tests for upsert_attachment()."""

    def test_dry_run_returns_dry_run_id(self):
        confluence = MagicMock()
        att_id = upsert_attachment(
            confluence, "123", "logo.png", b"data", "image/png", dry_run=True
        )
        assert att_id == "DRY-RUN"
        confluence.get_attachments_from_content.assert_not_called()
        confluence.attach_content.assert_not_called()

    def test_creates_when_no_existing_attachment(self):
        confluence = MagicMock()
        confluence.get_attachments_from_content.return_value = {"results": []}
        confluence.attach_content.return_value = {"results": [{"id": "att-99"}]}

        att_id = upsert_attachment(
            confluence,
            _PAGE_ID,
            "diagram.svg",
            b"<svg/>",
            "image/svg+xml",
            dry_run=False,
        )

        assert att_id == "att-99"
        confluence.get_attachments_from_content.assert_called_once_with(
            _PAGE_ID, filename="diagram.svg", limit=1
        )
        confluence.attach_content.assert_called_once_with(
            content=b"<svg/>",
            name="diagram.svg",
            content_type="image/svg+xml",
            page_id=_PAGE_ID,
        )
        confluence.update_attachment.assert_not_called()

    def test_updates_when_attachment_already_exists(self):
        confluence = MagicMock()
        confluence.get_attachments_from_content.return_value = {
            "results": [{"id": "att-42"}]
        }

        att_id = upsert_attachment(
            confluence, _PAGE_ID, "logo.png", b"bytes", "image/png", dry_run=False
        )

        assert att_id == "att-42"
        confluence.attach_content.assert_not_called()
        confluence.update_attachment.assert_called_once_with(
            page_id=_PAGE_ID,
            attachment_id="att-42",
            content=b"bytes",
            name="logo.png",
            content_type="image/png",
        )
