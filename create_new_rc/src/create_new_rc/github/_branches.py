"""Branch operations."""

from __future__ import annotations

from create_new_rc.github._client import gh


def branch_exists(repo: str, branch: str) -> bool:
    """Check if a branch exists in the repository.

    Args:
        repo: The repository in 'owner/repo' format.
        branch: The branch name.

    Returns:
        True if the branch exists, False otherwise.
    """
    try:
        gh("api", f"/repos/{repo}/branches/{branch}")
        return True
    except Exception:  # noqa: BLE001
        return False


def get_default_branch_sha(repo: str) -> str:
    """Get the commit SHA of the default branch (usually 'main').

    Args:
        repo: The repository in 'owner/repo' format.

    Returns:
        The commit SHA.

    Raises:
        GitHubAPIError: If the gh CLI call fails.
    """
    data = gh("api", f"/repos/{repo}")
    default_branch = data.get("default_branch", "main")
    branch_data = gh("api", f"/repos/{repo}/branches/{default_branch}")
    return branch_data["commit"]["sha"]


def get_branch_sha(repo: str, branch: str) -> str:
    """Get the commit SHA of a branch.

    Args:
        repo: The repository in 'owner/repo' format.
        branch: The branch name.

    Returns:
        The commit SHA.

    Raises:
        GitHubAPIError: If the gh CLI call fails.
    """
    data = gh("api", f"/repos/{repo}/branches/{branch}")
    return data["commit"]["sha"]


def get_commit_tree_sha(repo: str, commit_sha: str) -> str:
    """Get the tree SHA for a commit.

    Args:
        repo: The repository in 'owner/repo' format.
        commit_sha: The commit SHA.

    Returns:
        The tree SHA.

    Raises:
        GitHubAPIError: If the gh CLI call fails.
    """
    data = gh("api", f"/repos/{repo}/git/commits/{commit_sha}")
    return data["tree"]["sha"]


def create_branch(repo: str, branch: str, sha: str) -> None:
    """Create a new branch pointing to the specified commit.

    Args:
        repo: The repository in 'owner/repo' format.
        branch: The branch name.
        sha: The commit SHA.

    Raises:
        GitHubAPIError: If the gh CLI call fails.
    """
    gh(
        "api",
        "--method",
        "POST",
        f"/repos/{repo}/git/refs",
        "-f",
        f"ref=refs/heads/{branch}",
        "-f",
        f"sha={sha}",
    )


def create_empty_commit(
    repo: str,
    branch: str,
    message: str,
    parent_sha: str,
    tree_sha: str,
) -> str:
    """Create a verified empty commit via the GitHub API.

    Commits created through the API are automatically marked as verified by
    GitHub, satisfying 'commits must have verified signatures' branch
    protection rules without requiring a local GPG key.

    Args:
        repo: The repository in 'owner/repo' format.
        branch: The branch name.
        message: The commit message.
        parent_sha: The parent commit SHA (pre-resolved by caller).
        tree_sha: The tree SHA (pre-resolved by caller).

    Returns:
        The new commit SHA.

    Raises:
        GitHubAPIError: If the gh CLI call fails.
    """
    # Create the commit
    commit_data = gh(
        "api",
        "--method",
        "POST",
        f"/repos/{repo}/git/commits",
        "-f",
        f"message={message}",
        "-f",
        f"tree={tree_sha}",
        "-f",
        f"parents[]={parent_sha}",
    )
    new_sha = commit_data["sha"]

    # Advance the branch ref to the new commit
    gh(
        "api",
        "--method",
        "PATCH",
        f"/repos/{repo}/git/refs/heads/{branch}",
        "-f",
        f"sha={new_sha}",
        "-F",
        "force=false",
    )

    return new_sha
