"""Repository information helpers."""

from __future__ import annotations

from create_new_rc.github._client import gh


def get_repo(repo_arg: str | None) -> str:
    """Return owner/repo string.

    If repo_arg is provided, return it directly. Otherwise, fetch the
    current repository name from the gh CLI.

    Args:
        repo_arg: An explicit 'owner/repo' string, or None.

    Returns:
        The repository name in 'owner/repo' format.

    Raises:
        GitHubAPIError: If the gh CLI call fails.
    """
    if repo_arg:
        return repo_arg
    data = gh("repo", "view", "--json", "nameWithOwner")
    return data["nameWithOwner"]
