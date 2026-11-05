from __future__ import annotations

from unittest.mock import MagicMock, patch

from sync_confluence.confluence._constants import _Actions
from sync_confluence.confluence._page_dry_run import _upsert_page_dry_run
from sync_confluence.confluence._page_upsert import _create_new_page
from sync_confluence.confluence._properties import _content_hash
from sync_confluence.confluence._types import PageUpsertRequest


class TestCreateNewPageWidthHandling:
    """Tests for create flow width behavior in _create_new_page()."""

    @patch("sync_confluence.confluence._page_upsert._content_hash", return_value="h")
    @patch("sync_confluence.confluence._page_upsert._apply_page_width")
    @patch("sync_confluence.confluence._page_upsert._apply_page_metadata")
    def test_create_applies_width_after_metadata(
        self,
        mock_apply_metadata: MagicMock,
        mock_apply_width: MagicMock,
        mock_hash: MagicMock,
    ) -> None:
        confluence = MagicMock()
        confluence.create_page.return_value = {"id": "123"}
        request = PageUpsertRequest(
            space_key="DOCS",
            parent_id="1",
            title="My Page",
            body="<p>body</p>",
            page_width="full-width",
        )

        events: list[str] = []
        mock_apply_metadata.side_effect = lambda *args, **kwargs: events.append(
            "metadata"
        )
        mock_apply_width.side_effect = lambda *args, **kwargs: events.append("width")

        page_id, action = _create_new_page(confluence, request)

        assert page_id == "123"
        assert action == _Actions.CREATED
        mock_hash.assert_called_once_with(request.body)
        mock_apply_metadata.assert_called_once_with(
            confluence,
            "123",
            request,
            "h",
            apply_page_width=False,
        )
        mock_apply_width.assert_called_once_with(confluence, "123", "full-width")
        assert events == ["metadata", "width"]


class TestUpsertPageDryRunExistingPage:
    """A dry run must classify an existing page like a live run would."""

    def _request(self) -> PageUpsertRequest:
        return PageUpsertRequest(
            space_key="DOCS",
            parent_id="1",
            title="My Page",
            body="<p>body</p>",
            dry_run=True,
        )

    @patch("sync_confluence.confluence._page_dry_run._find_page_under_parent")
    @patch("sync_confluence.confluence._page_dry_run._fetch_hash_prop_value")
    def test_unchanged_when_hash_matches(
        self, mock_fetch: MagicMock, mock_find: MagicMock
    ) -> None:
        request = self._request()
        mock_find.return_value = {"id": "42"}
        mock_fetch.return_value = _content_hash(request.body)

        result = _upsert_page_dry_run(MagicMock(), request)

        assert result == ("42", _Actions.UNCHANGED)

    @patch("sync_confluence.confluence._page_dry_run._find_page_under_parent")
    @patch("sync_confluence.confluence._page_dry_run._fetch_hash_prop_value")
    def test_updated_when_hash_differs(
        self, mock_fetch: MagicMock, mock_find: MagicMock
    ) -> None:
        mock_find.return_value = {"id": "42"}
        mock_fetch.return_value = "stale"

        result = _upsert_page_dry_run(MagicMock(), self._request())

        assert result == ("42", _Actions.UPDATED)

    @patch("sync_confluence.confluence._page_dry_run._find_page_under_parent")
    def test_created_when_page_is_missing(self, mock_find: MagicMock) -> None:
        mock_find.return_value = None

        result = _upsert_page_dry_run(MagicMock(), self._request())

        assert result == ("DRY-RUN", _Actions.CREATED)
