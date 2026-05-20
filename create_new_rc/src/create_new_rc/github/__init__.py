"""GitHub API layer for release candidate management."""

from __future__ import annotations

from create_new_rc.github._branches import (
    branch_exists,
    create_branch,
    create_empty_commit,
    get_branch_sha,
    get_commit_tree_sha,
    get_default_branch_sha,
)
from create_new_rc.github._client import GitHubAPIError, gh
from create_new_rc.github._prs import create_pr, find_open_pr, is_release_merged
from create_new_rc.github._repo import get_repo
from create_new_rc.github._tags import create_tag, fetch_all_tags

__all__ = [
    "GitHubAPIError",
    "branch_exists",
    "create_branch",
    "create_empty_commit",
    "create_pr",
    "create_tag",
    "fetch_all_tags",
    "find_open_pr",
    "get_branch_sha",
    "get_commit_tree_sha",
    "get_default_branch_sha",
    "get_repo",
    "gh",
    "is_release_merged",
]
