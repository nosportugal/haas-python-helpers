"""Ensure the release branch exists with a commit ahead of main (phase 4)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from create_new_rc import github

log = logging.getLogger(__name__)


@dataclass
class _BranchResult:
    existed: bool
    sha: str


def _handle_existing_branch(repo: str, release_branch: str) -> str:
    """Ensure an existing branch has a commit ahead of main."""
    log.info("  Branch '%s' already exists.", release_branch)
    branch_sha = github.get_branch_sha(repo, release_branch)
    main_sha = github.get_default_branch_sha(repo)
    if branch_sha == main_sha:
        log.info("  Branch is at same commit as main — adding empty commit.")
        tree_sha = github.get_commit_tree_sha(repo, branch_sha)
        return github.create_empty_commit(
            repo,
            release_branch,
            f"chore: initialize {release_branch}",
            parent_sha=branch_sha,
            tree_sha=tree_sha,
        )
    return branch_sha


def _create_new_branch(repo: str, release_branch: str, dry_run: bool) -> str:
    """Create a new release branch from main with an initial commit."""
    if dry_run:
        log.info("  [DRY RUN] Would create branch '%s' from main.", release_branch)
        log.info("  [DRY RUN] Would add empty commit on '%s'.", release_branch)
        return "<sha-of-release>"
    branch_sha = github.get_default_branch_sha(repo)
    tree_sha = github.get_commit_tree_sha(repo, branch_sha)
    github.create_branch(repo, release_branch, branch_sha)
    return github.create_empty_commit(
        repo,
        release_branch,
        f"chore: initialize {release_branch}",
        parent_sha=branch_sha,
        tree_sha=tree_sha,
    )


def _check_exists(repo: str, release_branch: str, dry_run: bool) -> bool | None:
    """Return True/False whether the branch exists, or None on API error."""
    if dry_run:
        return False
    try:
        return github.branch_exists(repo, release_branch)
    except github.GitHubAPIError as exc:
        log.error("Error checking branch: %s", exc)
        return None


def _resolve_sha(
    repo: str, release_branch: str, dry_run: bool, exists: bool
) -> str | None:
    """Get or create the branch SHA. Returns None on API error."""
    try:
        return (
            _handle_existing_branch(repo, release_branch)
            if exists
            else _create_new_branch(repo, release_branch, dry_run)
        )
    except github.GitHubAPIError as exc:
        log.error("Error: %s", exc)
        return None


def prepare_branch(
    repo: str,
    release_branch: str,
    dry_run: bool,
    prefix: str,
) -> _BranchResult | None:
    """Ensure the release branch exists. Returns (existed, sha) or None on error."""
    log.info("%sChecking release branch…", prefix)
    exists = _check_exists(repo, release_branch, dry_run)
    if exists is None:
        return None
    sha = _resolve_sha(repo, release_branch, dry_run, exists)
    if sha is None:
        return None
    log.info("")
    return _BranchResult(existed=exists, sha=sha)
