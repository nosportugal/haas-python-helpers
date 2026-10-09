"""Tag operations."""

from __future__ import annotations

from create_new_rc._models import ParsedTag, parse_tag
from create_new_rc.github._client import gh


def fetch_all_tags(repo: str) -> list[ParsedTag]:
    """Fetch all tags from the repo and return parsed RC tags.

    Handles pagination automatically (100 tags per page).

    Args:
        repo: The repository in 'owner/repo' format.

    Returns:
        A list of ParsedTag objects (only RC tags; other tags are filtered out).

    Raises:
        GitHubAPIError: If the gh CLI call fails.
    """
    page = 1
    parsed = []
    while True:
        tags = gh("api", f"/repos/{repo}/tags?per_page=100&page={page}")
        if not isinstance(tags, list) or not tags:
            break
        for t in tags:
            p = parse_tag(t["name"])
            if p:
                parsed.append(p)
        if len(tags) < 100:
            break
        page += 1
    return parsed


def create_tag(repo: str, tag: str, sha: str) -> None:
    """Create a new git tag at the specified commit.

    Args:
        repo: The repository in 'owner/repo' format.
        tag: The tag name (e.g., 'v2026.2.0-rc3').
        sha: The commit SHA to tag.

    Raises:
        GitHubAPIError: If the gh CLI call fails.
    """
    gh(
        "api",
        "--method",
        "POST",
        f"/repos/{repo}/git/refs",
        "-f",
        f"ref=refs/tags/{tag}",
        "-f",
        f"sha={sha}",
    )
