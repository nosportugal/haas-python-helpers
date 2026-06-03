from __future__ import annotations

from unittest.mock import MagicMock, patch

from sync_confluence.confluence._constants import (
    _APPEARANCE_DRAFT_KEY,
    _APPEARANCE_PUBLISHED_KEY,
)
from sync_confluence.confluence._page_metadata import (
    _apply_page_metadata,
    _apply_page_width,
)
from sync_confluence.confluence._types import PageUpsertRequest

_PATCH_PATH = "sync_confluence.confluence._page_metadata._try_property_set"
_PAGE_ID = "42"
_BODY_HASH = "abc123"
_FULL_WIDTH = "full-width"
_DEFAULT_WIDTH = "default"
_APPEARANCE_KEYS = frozenset((_APPEARANCE_PUBLISHED_KEY, _APPEARANCE_DRAFT_KEY))


def _make_request(**overrides: object) -> PageUpsertRequest:
    defaults: dict[str, object] = {
        "space_key": "DOCS",
        "parent_id": "1",
        "title": "Test Page",
        "body": "<p>body</p>",
    }
    defaults.update(overrides)
    return PageUpsertRequest(**defaults)  # type: ignore[arg-type]


def _appearance_values(mock_set: MagicMock) -> list[str]:
    return [
        called.args[3]
        for called in mock_set.call_args_list
        if called.args[2] in _APPEARANCE_KEYS
    ]


class TestApplyPageMetadataAppearance:
    """Tests for appearance property serialization in _apply_page_metadata()."""

    @patch(_PATCH_PATH)
    def test_full_width_stores_plain_value(self, mock_set: MagicMock) -> None:
        confluence = MagicMock()
        request = _make_request(page_width=_FULL_WIDTH)
        _apply_page_metadata(confluence, _PAGE_ID, request, _BODY_HASH)
        raw_values = _appearance_values(mock_set)
        assert len(raw_values) == 2
        assert all(raw == _FULL_WIDTH for raw in raw_values)

    @patch(_PATCH_PATH)
    def test_default_width_stores_plain_value(self, mock_set: MagicMock) -> None:
        confluence = MagicMock()
        request = _make_request(page_width=_DEFAULT_WIDTH)
        _apply_page_metadata(confluence, _PAGE_ID, request, _BODY_HASH)
        raw_values = _appearance_values(mock_set)
        assert len(raw_values) == 2
        assert all(raw == _DEFAULT_WIDTH for raw in raw_values)

    @patch(_PATCH_PATH)
    def test_both_published_and_draft_keys_set(self, mock_set: MagicMock) -> None:
        confluence = MagicMock()
        request = _make_request(page_width=_FULL_WIDTH)
        _apply_page_metadata(confluence, _PAGE_ID, request, _BODY_HASH)
        keys_set = {called.args[2] for called in mock_set.call_args_list}
        assert _APPEARANCE_PUBLISHED_KEY in keys_set
        assert _APPEARANCE_DRAFT_KEY in keys_set

    @patch(_PATCH_PATH)
    def test_none_page_width_omits_appearance(self, mock_set: MagicMock) -> None:
        confluence = MagicMock()
        request = _make_request(page_width=None)
        _apply_page_metadata(confluence, _PAGE_ID, request, _BODY_HASH)
        assert _appearance_values(mock_set) == []

    @patch(_PATCH_PATH)
    def test_value_is_not_json_payload(self, mock_set: MagicMock) -> None:
        confluence = MagicMock()
        request = _make_request(page_width=_FULL_WIDTH)
        _apply_page_metadata(confluence, _PAGE_ID, request, _BODY_HASH)
        for raw in _appearance_values(mock_set):
            assert not raw.startswith("{"), "value must be plain width, not JSON"

    @patch(_PATCH_PATH)
    def test_apply_page_width_false_omits_appearance(self, mock_set: MagicMock) -> None:
        confluence = MagicMock()
        request = _make_request(page_width=_FULL_WIDTH)
        _apply_page_metadata(
            confluence,
            _PAGE_ID,
            request,
            _BODY_HASH,
            apply_page_width=False,
        )
        assert _appearance_values(mock_set) == []


class TestApplyPageWidth:
    """Tests for dedicated page width post-create application helper."""

    @patch(_PATCH_PATH)
    def test_none_width_does_nothing(self, mock_set: MagicMock) -> None:
        _apply_page_width(MagicMock(), _PAGE_ID, None)
        assert mock_set.call_count == 0

    @patch(_PATCH_PATH)
    def test_width_sets_published_and_draft(self, mock_set: MagicMock) -> None:
        _apply_page_width(MagicMock(), _PAGE_ID, _FULL_WIDTH)
        keys_set = {called.args[2] for called in mock_set.call_args_list}
        assert _APPEARANCE_PUBLISHED_KEY in keys_set
        assert _APPEARANCE_DRAFT_KEY in keys_set
