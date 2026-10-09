"""Tests for github/ subpackage."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from create_new_rc import github

_REPO_OWNER_REPO = "owner/repo"
_TAG_V2026_2_0_RC1 = "v2026.2.0-rc1"
_TAG_V2026_2_0_RC0 = "v2026.2.0-rc0"
_TAG_V2026_1_0_RC1 = "v2026.1.0-rc1"
_TAG_V2026_2_0_H1_RC0 = "v2026.2.0-h1-rc0"
_TAG_V2026_2_0_H2_RC0 = "v2026.2.0-h2-rc0"
_SHA_ABC123 = "abc123"
_BRANCH_MAIN = "main"
_BRANCH_RELEASE = "release/v2026.2.0"
_ENDPOINT_BASE = "create_new_rc.github._"
_API_METHOD = "api"
_JSON_RESPONSE = '{"key": "value"}'
_PLAIN_TEXT_RESPONSE = "plain text response"
_FIRST_PAGE_ITEMS = 100
_SECOND_PAGE_ITEMS = 50
_NAME_KEY = "name"
_HEAD_REF_NAME_KEY = "headRefName"
_PR_FEATURE_BRANCH_NUMBER = 123
_PR_RELEASE_BRANCH_NUMBER = 124


class TestGh:
    """Tests for the gh() subprocess wrapper."""

    @patch(f"{_ENDPOINT_BASE}client.subprocess.run")
    def test_gh_json_output(self, mock_run: MagicMock) -> None:
        """gh() parses JSON output."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=_JSON_RESPONSE,
            stderr="",
        )
        parsed_output = github.gh(_API_METHOD, "/some/endpoint")
        assert parsed_output == {"key": "value"}
        mock_run.assert_called_once()

    @patch(f"{_ENDPOINT_BASE}client.subprocess.run")
    def test_gh_plain_text_output(self, mock_run: MagicMock) -> None:
        """gh() returns plain text when JSON parsing fails."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=_PLAIN_TEXT_RESPONSE,
            stderr="",
        )
        parsed_output = github.gh("pr", "create")
        assert parsed_output == _PLAIN_TEXT_RESPONSE

    @patch(f"{_ENDPOINT_BASE}client.subprocess.run")
    def test_gh_error(self, mock_run: MagicMock) -> None:
        """gh() raises GitHubAPIError on non-zero exit."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="error message",
        )
        with pytest.raises(github.GitHubAPIError, match="error message"):
            github.gh(_API_METHOD, "/some/endpoint")


class TestFetchAllTags:
    """Tests for fetch_all_tags()."""

    @patch(f"{_ENDPOINT_BASE}tags.gh")
    def test_fetch_all_tags_single_page(self, mock_gh: MagicMock) -> None:
        """Fetch tags from a single page."""
        mock_gh.return_value = [
            {_NAME_KEY: _TAG_V2026_1_0_RC1},
            {_NAME_KEY: _TAG_V2026_2_0_RC0},
            {_NAME_KEY: "non-rc-tag"},  # filtered out
        ]
        parsed_tags = github.fetch_all_tags(_REPO_OWNER_REPO)
        assert len(parsed_tags) == 2
        assert parsed_tags[0].base_version == "v2026.1.0"
        assert parsed_tags[1].base_version == "v2026.2.0"

    @patch(f"{_ENDPOINT_BASE}tags.gh")
    def test_fetch_all_tags_pagination(self, mock_gh: MagicMock) -> None:
        """Fetch tags across multiple pages."""
        page_one = [{"name": f"v2026.1.0-rc{idx}"} for idx in range(_FIRST_PAGE_ITEMS)]
        page_two = [{"name": f"v2026.2.0-rc{idx}"} for idx in range(_SECOND_PAGE_ITEMS)]
        mock_gh.side_effect = [page_one, page_two]

        parsed_tags = github.fetch_all_tags(_REPO_OWNER_REPO)
        expected_total = _FIRST_PAGE_ITEMS + _SECOND_PAGE_ITEMS
        assert len(parsed_tags) == expected_total


class TestBranchExists:
    """Tests for branch_exists()."""

    @patch(f"{_ENDPOINT_BASE}branches.gh")
    def test_branch_exists_true(self, mock_gh: MagicMock) -> None:
        """Return True if branch exists."""
        mock_gh.return_value = {"name": _BRANCH_MAIN}
        branch_present = github.branch_exists(_REPO_OWNER_REPO, _BRANCH_MAIN)
        assert branch_present is True

    @patch(f"{_ENDPOINT_BASE}branches.gh")
    def test_branch_exists_false(self, mock_gh: MagicMock) -> None:
        """Return False if branch does not exist."""
        mock_gh.side_effect = Exception("Not found")
        branch_present = github.branch_exists(_REPO_OWNER_REPO, "nonexistent")
        assert branch_present is False


class TestGetRepo:
    """Tests for get_repo()."""

    def test_get_repo_explicit(self) -> None:
        """Return explicit repo if provided."""
        parsed_repo = github.get_repo(_REPO_OWNER_REPO)
        assert parsed_repo == _REPO_OWNER_REPO

    @patch(f"{_ENDPOINT_BASE}repo.gh")
    def test_get_repo_inferred(self, mock_gh: MagicMock) -> None:
        """Infer repo from gh CLI if not provided."""
        mock_gh.return_value = {"nameWithOwner": "inferred/repo"}
        parsed_repo = github.get_repo(None)
        assert parsed_repo == "inferred/repo"


class TestFindOpenPr:
    """Tests for find_open_pr()."""

    @patch(f"{_ENDPOINT_BASE}prs.gh")
    def test_find_open_pr_found(self, mock_gh: MagicMock) -> None:
        """Find an open PR."""
        mock_gh.return_value = [
            {"number": _PR_FEATURE_BRANCH_NUMBER, _HEAD_REF_NAME_KEY: "feature-branch"},
            {"number": _PR_RELEASE_BRANCH_NUMBER, _HEAD_REF_NAME_KEY: _BRANCH_RELEASE},
        ]
        pr_number = github.find_open_pr(_REPO_OWNER_REPO, _BRANCH_MAIN, _BRANCH_RELEASE)
        assert pr_number == _PR_RELEASE_BRANCH_NUMBER

    @patch(f"{_ENDPOINT_BASE}prs.gh")
    def test_find_open_pr_not_found(self, mock_gh: MagicMock) -> None:
        """Return None if no matching PR."""
        mock_gh.return_value = [
            {"number": 123, "headRefName": "feature-branch"},
        ]
        pr_number = github.find_open_pr(_REPO_OWNER_REPO, _BRANCH_MAIN, _BRANCH_RELEASE)
        assert pr_number is None


class TestIsReleaseMerged:
    """Tests for is_release_merged()."""

    @patch(f"{_ENDPOINT_BASE}prs.gh")
    def test_is_release_merged_true(self, mock_gh: MagicMock) -> None:
        """Return True if release branch was merged."""
        mock_gh.return_value = [
            {"headRefName": _BRANCH_RELEASE},
        ]
        is_merged = github.is_release_merged(_REPO_OWNER_REPO, "v2026.2.0")
        assert is_merged is True

    @patch(f"{_ENDPOINT_BASE}prs.gh")
    def test_is_release_merged_false(self, mock_gh: MagicMock) -> None:
        """Return False if release branch was not merged."""
        mock_gh.return_value = [
            {"headRefName": "release/v2026.1.0"},
        ]
        is_merged = github.is_release_merged(_REPO_OWNER_REPO, "v2026.2.0")
        assert is_merged is False
