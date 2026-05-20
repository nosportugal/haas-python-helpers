"""Tests for github operations: tags, branches, commits."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from create_new_rc import github

_REPO_OWNER_REPO = "owner/repo"
_TAG_V2026_2_0_RC1 = "v2026.2.0-rc1"
_SHA_ABC123 = "abc123"
_SHA_NEW = "new-sha"
_SHA_PARENT = "parent-sha"
_SHA_TREE = "tree-sha"
_BRANCH_RELEASE = "release/v2026.2.0"
_ENDPOINT_BASE = "create_new_rc.github._"
_API_METHOD = "api"
_POST_METHOD = "POST"
_GIT_REFS_ENDPOINT = "/repos/{repo}/git/refs"
_REF_FLAG = "-f"
_REF_TAGS_PREFIX = "refs/tags/"
_REF_HEADS_PREFIX = "refs/heads/"
_REF_KEY = "ref"
_SHA_KEY = "sha"


class TestCreateTag:
    """Tests for create_tag()."""

    @patch(f"{_ENDPOINT_BASE}tags.gh")
    def test_create_tag(self, mock_gh: MagicMock) -> None:
        """Create a tag."""
        github.create_tag(_REPO_OWNER_REPO, _TAG_V2026_2_0_RC1, _SHA_ABC123)
        mock_gh.assert_called_once_with(
            _API_METHOD,
            "--method",
            _POST_METHOD,
            _GIT_REFS_ENDPOINT.format(repo=_REPO_OWNER_REPO),
            _REF_FLAG,
            f"{_REF_KEY}={_REF_TAGS_PREFIX}{_TAG_V2026_2_0_RC1}",
            _REF_FLAG,
            f"{_SHA_KEY}={_SHA_ABC123}",
        )


class TestCreateBranch:
    """Tests for create_branch()."""

    @patch(f"{_ENDPOINT_BASE}branches.gh")
    def test_create_branch(self, mock_gh: MagicMock) -> None:
        """Create a branch."""
        github.create_branch(_REPO_OWNER_REPO, _BRANCH_RELEASE, _SHA_ABC123)
        mock_gh.assert_called_once_with(
            _API_METHOD,
            "--method",
            _POST_METHOD,
            _GIT_REFS_ENDPOINT.format(repo=_REPO_OWNER_REPO),
            _REF_FLAG,
            f"{_REF_KEY}={_REF_HEADS_PREFIX}{_BRANCH_RELEASE}",
            _REF_FLAG,
            f"{_SHA_KEY}={_SHA_ABC123}",
        )


class TestCreateEmptyCommit:
    """Tests for create_empty_commit()."""

    @patch(f"{_ENDPOINT_BASE}branches.gh")
    def test_create_empty_commit(self, mock_gh: MagicMock) -> None:
        """Create an empty commit."""
        mock_gh.side_effect = [
            {_SHA_KEY: _SHA_NEW},  # commit creation response
            {},  # ref update response
        ]
        commit_sha = github.create_empty_commit(
            _REPO_OWNER_REPO,
            _BRANCH_RELEASE,
            "chore: message",
            _SHA_PARENT,
            _SHA_TREE,
        )
        assert commit_sha == _SHA_NEW
        assert mock_gh.call_count == 2
