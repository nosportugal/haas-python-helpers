"""Pull request operations."""

from __future__ import annotations

from create_new_rc.github._client import gh


def find_open_pr(repo: str, base: str, head_branch: str) -> int | None:
    """Find an open PR with the given base and head branch.

    Args:
        repo: The repository in 'owner/repo' format.
        base: The base branch (e.g., 'main').
        head_branch: The head branch name.

    Returns:
        The PR number if found, None otherwise.

    Raises:
        GitHubAPIError: If the gh CLI call fails.
    """
    data = gh(
        "pr",
        "list",
        "--repo",
        repo,
        "--base",
        base,
        "--state",
        "open",
        "--json",
        "number,headRefName",
    )
    if not isinstance(data, list):
        return None
    for pr in data:
        if pr.get("headRefName") == head_branch:
            return pr["number"]
    return None


def is_release_merged(repo: str, base_version: str) -> bool:
    """Check if the release branch for a base version was merged.

    Args:
        repo: The repository in 'owner/repo' format.
        base_version: The base version (e.g., 'v2026.2.0').

    Returns:
        True if the release branch was merged into main, False otherwise.

    Raises:
        GitHubAPIError: If the gh CLI call fails.
    """
    head_branch = f"release/{base_version}"
    data = gh(
        "pr",
        "list",
        "--repo",
        repo,
        "--base",
        "main",
        "--state",
        "merged",
        "--json",
        "headRefName",
    )
    if not isinstance(data, list):
        return False
    return any(pr.get("headRefName") == head_branch for pr in data)


def create_pr(repo: str, base_version: str, branch: str) -> None:
    """Create a release PR.

    Args:
        repo: The repository in 'owner/repo' format.
        base_version: The base version (e.g., 'v2026.2.0').
        branch: The head branch name.

    Raises:
        GitHubAPIError: If the gh CLI call fails.
    """
    title = f"Release {base_version}"
    body = (
        f"Automated release PR for **{base_version}**.\n\n"
        "This PR was created by `create-rc` and will be referenced "
        "by E2E dispatch workflows triggered from RC tags."
    )
    result = gh(
        "pr",
        "create",
        "--repo",
        repo,
        "--base",
        "main",
        "--head",
        branch,
        "--title",
        title,
        "--body",
        body,
    )
    if isinstance(result, str) and result.startswith("http"):
        # Print the URL for user feedback (handled in _main.py)
        pass
