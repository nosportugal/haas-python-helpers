from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest
from requests import HTTPError, Response

from sync_confluence.confluence import (
    DeleteOrphansRequest,
    FolderConflictError,
    FolderNotOwnedError,
    FolderUpsertRequest,
    PageSyncAction,
    delete_orphans,
    ensure_folder_owned,
    find_owned_folder,
    upsert_folder,
)
from sync_confluence.confluence._folder_create import _create_folder_with_fallback
from sync_confluence.confluence.sync_cli import resolve_managed_by_label

_CLEANUP = "sync_confluence.confluence._cleanup"
_FOLDER_FALLBACK = "sync_confluence.confluence._folder_fallback"
_PAGES = [
    {"id": "1", "title": "1.1 - Old (Cisco, L3VPN)"},
    {"id": "2", "title": "1.1 - Other (Cisco, L2VPN)"},
    {"id": "3", "title": "Markdown page"},
]
_SOURCE_PATHS = {
    "1": "testspec/L3VPN/Cisco/1.1",
    "2": "testspec/L2VPN/Cisco/1.1",
    "3": "docs/page.md",
}


@patch(f"{_CLEANUP}._page_has_label", return_value=True)
@patch(f"{_CLEANUP}._get_source_path_property")
@patch(f"{_CLEANUP}._collect_children", return_value=_PAGES)
def test_delete_orphans_only_deletes_inside_source_path_prefix(
    mock_children: MagicMock, mock_path: MagicMock, mock_label: MagicMock
) -> None:
    mock_path.side_effect = lambda _confluence, page_id: _SOURCE_PATHS[page_id]
    confluence = MagicMock()
    request = DeleteOrphansRequest(
        root_page_id="100",
        expected_titles=set(),
        managed_by_label="managed-by-x",
        expected_paths=set(),
        source_path_prefix="testspec/L3VPN/",
    )

    assert delete_orphans(confluence, request) == 1
    confluence.remove_page.assert_called_once_with("1")


@patch(f"{_CLEANUP}._page_has_label", return_value=True)
@patch(f"{_CLEANUP}._get_source_path_property", return_value=None)
@patch(f"{_CLEANUP}._collect_children", return_value=_PAGES[:1])
def test_delete_orphans_keeps_pages_without_source_path_when_scoped(
    mock_children: MagicMock, mock_path: MagicMock, mock_label: MagicMock
) -> None:
    confluence = MagicMock()
    request = DeleteOrphansRequest(
        root_page_id="100",
        expected_titles=set(),
        source_path_prefix="testspec/L3VPN/",
    )

    assert delete_orphans(confluence, request) == 0
    confluence.remove_page.assert_not_called()


@patch(f"{_CLEANUP}._page_has_label", return_value=True)
@patch(f"{_CLEANUP}._get_source_path_property")
@patch(f"{_CLEANUP}._collect_children", return_value=_PAGES)
def test_delete_orphans_without_prefix_keeps_previous_behaviour(
    mock_children: MagicMock, mock_path: MagicMock, mock_label: MagicMock
) -> None:
    mock_path.side_effect = lambda _confluence, page_id: _SOURCE_PATHS[page_id]
    confluence = MagicMock()
    request = DeleteOrphansRequest(
        root_page_id="100",
        expected_titles=set(),
        expected_paths={"docs/page.md"},
    )

    assert delete_orphans(confluence, request) == 2
    assert [c.args[0] for c in confluence.remove_page.call_args_list] == ["1", "2"]


def _folder_exists_error() -> HTTPError:
    response = Response()
    response.status_code = 400
    return HTTPError("A folder with this title already exists", response=response)


def _folder_request() -> FolderUpsertRequest:
    return FolderUpsertRequest(space_key="HaaS", parent_id="100", title="Cisco (L3VPN)")


@pytest.mark.parametrize("ancestors", [[{"id": "999"}], []])
@patch(f"{_FOLDER_FALLBACK}._find_folder_by_space_cql", return_value="55")
def test_fallback_refuses_folder_under_another_parent(
    mock_cql: MagicMock, ancestors: list[dict]
) -> None:
    confluence = MagicMock()
    confluence.post.side_effect = _folder_exists_error()
    confluence.get.return_value = {"id": "55", "ancestors": ancestors}

    with pytest.raises(FolderConflictError, match="not under parent 100"):
        _create_folder_with_fallback(confluence, _folder_request())


@patch(f"{_FOLDER_FALLBACK}._find_folder_by_space_cql", return_value="55")
def test_fallback_reuses_folder_under_the_requested_parent(
    mock_cql: MagicMock,
) -> None:
    confluence = MagicMock()
    confluence.post.side_effect = _folder_exists_error()
    confluence.get.return_value = {"id": "55", "ancestors": [{"id": 1}, {"id": 100}]}

    folder = _create_folder_with_fallback(confluence, _folder_request())

    assert folder == ("55", PageSyncAction.UNCHANGED)


@pytest.mark.parametrize(
    ("managed_by", "expected"),
    [
        (None, "managed-by-repo-testspec"),
        ("custom-label", "custom-label"),
    ],
)
def test_label_suffix_applies_only_to_derived_label(
    managed_by: str | None, expected: str
) -> None:
    args = argparse.Namespace(managed_by=managed_by)

    label = resolve_managed_by_label(args, "https://github.com/org/repo", "-testspec")

    assert label == expected


_FOLDER_UPSERT = "sync_confluence.confluence._folder_upsert"
_OWNERSHIP = "sync_confluence.confluence._folder_ownership"


def _owned_request(require_ownership: bool = True) -> FolderUpsertRequest:
    return FolderUpsertRequest(
        space_key="HaaS",
        parent_id="100",
        title="Cisco (L3VPN)",
        managed_by_label="managed-by-repo-testspec",
        require_ownership=require_ownership,
    )


@patch(f"{_FOLDER_UPSERT}._try_property_set")
@patch(f"{_FOLDER_UPSERT}._apply_label")
@patch(f"{_OWNERSHIP}._page_has_label", return_value=False)
@patch(f"{_FOLDER_UPSERT}.find_folder_under_parent", return_value={"id": "7"})
def test_upsert_folder_refuses_unlabelled_existing_folder(
    mock_find: MagicMock,
    mock_has_label: MagicMock,
    mock_apply: MagicMock,
    mock_property: MagicMock,
) -> None:
    with pytest.raises(FolderNotOwnedError, match="has no 'managed-by-repo-testspec'"):
        upsert_folder(MagicMock(), _owned_request())

    mock_apply.assert_not_called()


@pytest.mark.parametrize(
    ("require_ownership", "has_label"), [(True, True), (False, False)]
)
@patch(f"{_FOLDER_UPSERT}._try_property_set")
@patch(f"{_FOLDER_UPSERT}._apply_label")
@patch(f"{_OWNERSHIP}._page_has_label")
@patch(f"{_FOLDER_UPSERT}.find_folder_under_parent", return_value={"id": "7"})
def test_upsert_folder_reuses_owned_or_unchecked_folder(
    mock_find: MagicMock,
    mock_has_label: MagicMock,
    mock_apply: MagicMock,
    mock_property: MagicMock,
    require_ownership: bool,
    has_label: bool,
) -> None:
    mock_has_label.return_value = has_label

    folder = upsert_folder(MagicMock(), _owned_request(require_ownership))

    assert folder == ("7", PageSyncAction.UNCHANGED)
    mock_apply.assert_called_once()


@patch(f"{_OWNERSHIP}._page_has_label", return_value=False)
@patch(f"{_FOLDER_FALLBACK}._find_folder_by_space_cql", return_value="55")
def test_fallback_refuses_unlabelled_folder_under_the_parent(
    mock_cql: MagicMock, mock_has_label: MagicMock
) -> None:
    confluence = MagicMock()
    confluence.post.side_effect = _folder_exists_error()
    confluence.get.return_value = {"id": "55", "ancestors": [{"id": "100"}]}

    with pytest.raises(FolderNotOwnedError):
        _create_folder_with_fallback(confluence, _owned_request())


def test_ownership_fails_closed_without_a_label() -> None:
    confluence = MagicMock()
    request = FolderUpsertRequest(
        space_key="HaaS", parent_id="100", title="X", require_ownership=True
    )

    with pytest.raises(FolderNotOwnedError, match="no managed-by label"):
        ensure_folder_owned(confluence, "7", request)

    confluence.get.assert_not_called()


def test_ownership_is_not_checked_when_not_required() -> None:
    request = FolderUpsertRequest(space_key="HaaS", parent_id="100", title="X")

    ensure_folder_owned(MagicMock(), "7", request)


@patch(f"{_FOLDER_FALLBACK}._find_folder_by_space_cql", return_value="55")
@patch(f"{_FOLDER_FALLBACK}.find_folder_under_parent", return_value=None)
def test_find_owned_folder_rejects_same_title_under_another_parent(
    mock_find: MagicMock, mock_cql: MagicMock
) -> None:
    confluence = MagicMock()
    confluence.get.return_value = {"id": "55", "ancestors": [{"id": "999"}]}

    with pytest.raises(FolderConflictError, match="not under parent 100"):
        find_owned_folder(confluence, _owned_request())


@patch(f"{_FOLDER_FALLBACK}._find_folder_by_space_cql", return_value=None)
@patch(f"{_FOLDER_FALLBACK}.find_folder_under_parent", return_value=None)
def test_find_owned_folder_returns_none_when_title_is_free(
    mock_find: MagicMock, mock_cql: MagicMock
) -> None:
    assert find_owned_folder(MagicMock(), _owned_request()) is None
