"""Create the RC tag and open the release PR (phases 5 and 6)."""

from __future__ import annotations

import logging

from create_new_rc import github
from create_new_rc.cli._compute import _PlanResult

log = logging.getLogger(__name__)


def _log_existing_pr(repo: str, pr_number: int) -> None:
    log.info(
        "  Open PR already exists: #%d — https://github.com/%s/pull/%d",
        pr_number,
        repo,
        pr_number,
    )


def _create_or_log_pr(repo: str, plan: _PlanResult, dry_run: bool) -> int:
    if dry_run:
        log.info(
            "  [DRY RUN] Would create PR: 'Release %s' (%s → main).",
            plan.resolved_bv,
            plan.release_branch,
        )
        return 0
    try:
        github.create_pr(repo, plan.resolved_bv, plan.release_branch)
    except github.GitHubAPIError as exc:
        log.error("Error creating PR: %s", exc)
        return 1
    log.info(
        "  PR created: https://github.com/%s/compare/main...%s",
        repo,
        plan.release_branch,
    )
    return 0


def _handle_pr_result(
    repo: str, existing_pr: int | None, plan: _PlanResult, dry_run: bool
) -> int:
    if existing_pr:
        _log_existing_pr(repo, existing_pr)
        return 0
    return _create_or_log_pr(repo, plan, dry_run)


def ensure_pr(repo: str, plan: _PlanResult, dry_run: bool, prefix: str) -> int:
    """Find or create the release PR. Returns 0 on success, 1 on error."""
    log.info("%sChecking for existing PR…", prefix)
    try:
        if dry_run:
            existing_pr: int | None = None
        else:
            existing_pr = github.find_open_pr(repo, "main", plan.release_branch)
    except github.GitHubAPIError as exc:
        log.error("Error checking PRs: %s", exc)
        return 1
    code = _handle_pr_result(repo, existing_pr, plan, dry_run)
    log.info("")
    return code


def publish_tag(
    repo: str, plan: _PlanResult, branch_sha: str, dry_run: bool, prefix: str
) -> int:
    """Create the RC tag. Returns 0 on success, 1 on error."""
    log.info("%sCreating tag…", prefix)
    if dry_run:
        log.info("  [DRY RUN] Would create tag '%s'.", plan.next_tag)
    else:
        try:
            github.create_tag(repo, plan.next_tag, branch_sha)
        except github.GitHubAPIError as exc:
            log.error("Error creating tag: %s", exc)
            return 1
    log.info("")
    return 0
