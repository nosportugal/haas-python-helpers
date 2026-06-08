from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from sync_confluence.confluence import upload_attachments
from sync_confluence.converter import Attachment

_PAGE_ID = "P1"
_KEEP = "keep.png"


class TestUploadAttachments:
    """Tests for upload_attachments() upload + reconcile."""

    def test_uploads_and_deletes_unreferenced(self):
        confluence = MagicMock()
        confluence.get_attachments_from_content.return_value = {
            "results": [
                {"title": "stale.png", "id": "1"},
                {"title": _KEEP, "id": "2"},
            ]
        }
        attachments = [Attachment(name=_KEEP, path=Path("/x") / _KEEP)]
        upload_attachments(confluence, _PAGE_ID, attachments)
        confluence.attach_file.assert_called_once_with(
            str(Path("/x") / _KEEP), name=_KEEP, page_id=_PAGE_ID
        )
        confluence.delete_attachment.assert_called_once_with(_PAGE_ID, "stale.png")

    def test_dry_run_makes_no_calls(self):
        confluence = MagicMock()
        upload_attachments(
            confluence,
            _PAGE_ID,
            [Attachment(name="a.png", path=Path("/x/a.png"))],
            dry_run=True,
        )
        confluence.attach_file.assert_not_called()
        confluence.delete_attachment.assert_not_called()

    def test_raw_bytes_uses_attach_content(self):
        confluence = MagicMock()
        confluence.get_attachments_from_content.return_value = {"results": []}
        raw = b"\x89PNG"
        attachment = Attachment(
            name="mermaid-abc123.png",
            path=None,
            raw_bytes=raw,
            content_type="image/png",
        )
        upload_attachments(confluence, _PAGE_ID, [attachment])
        confluence.attach_content.assert_called_once_with(
            content=raw,
            name="mermaid-abc123.png",
            content_type="image/png",
            page_id=_PAGE_ID,
        )
        confluence.attach_file.assert_not_called()

    def test_path_attachment_uses_attach_file(self):
        confluence = MagicMock()
        confluence.get_attachments_from_content.return_value = {"results": []}
        attachment = Attachment(name="img.png", path=Path("/docs/img.png"))
        upload_attachments(confluence, _PAGE_ID, [attachment])
        confluence.attach_file.assert_called_once()
        confluence.attach_content.assert_not_called()
