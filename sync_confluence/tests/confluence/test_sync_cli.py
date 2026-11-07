from __future__ import annotations

from typing import Callable
from unittest.mock import MagicMock, patch

import pytest

from sync_confluence.confluence.sync_cli import (
    ConfluenceSession,
    finalise_sync_run,
    new_sync_result,
)
from sync_confluence.markdown.cli import parse_markdown_sync_args
from sync_confluence.testspec import parse_testspec_sync_args

_PARSERS = [parse_markdown_sync_args, parse_testspec_sync_args]


@pytest.mark.parametrize("parse", _PARSERS)
@pytest.mark.parametrize("width", ["wide", "max"])
def test_invalid_page_width_from_env_is_rejected(
    parse: Callable, width: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CONFLUENCE_PAGE_WIDTH", width)

    with pytest.raises(SystemExit) as exc_info:
        parse([])

    assert exc_info.value.code == 2


@pytest.mark.parametrize("parse", _PARSERS)
def test_valid_page_width_from_env_is_accepted(
    parse: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CONFLUENCE_PAGE_WIDTH", "default")

    assert parse([]).page_width == "default"


def _session() -> ConfluenceSession:
    return ConfluenceSession(
        confluence=MagicMock(),
        repo_url=None,
        managed_by_label="managed-by-x",
        restrict_edits_to="acc",
    )


@patch("sync_confluence.confluence.sync_cli._finalise_sync_run.delete_orphans")
def test_cleanup_is_skipped_when_any_page_was_skipped(
    mock_delete: MagicMock,
) -> None:
    sync_result = new_sync_result()
    sync_result.skipped.append("1.1 - Moved (Nokia)")

    finalise_sync_run(sync_result, _session(), "100", dry_run=False)

    mock_delete.assert_not_called()


@patch(
    "sync_confluence.confluence.sync_cli._finalise_sync_run.delete_orphans",
    return_value=0,
)
def test_cleanup_runs_when_nothing_was_skipped(mock_delete: MagicMock) -> None:
    sync_result = new_sync_result()
    sync_result.expected_titles.add("Page")

    finalise_sync_run(sync_result, _session(), "100", dry_run=False)

    request = mock_delete.call_args.args[1]
    assert request.root_page_id == "100"
    assert request.expected_titles == {"Page"}
    assert request.managed_by_label == "managed-by-x"
