"""Compute the next RC tag and release plan (phase 3)."""

from __future__ import annotations

import logging
from argparse import Namespace
from dataclasses import dataclass
from datetime import date

from create_new_rc import github
from create_new_rc._models import ParsedTag
from create_new_rc._version import bump_minor, compute_next_hotfix, compute_next_regular

log = logging.getLogger(__name__)


@dataclass
class _PlanResult:
    next_tag: str
    resolved_bv: str
    release_branch: str


def _latest_base_version(all_tags: list[ParsedTag]) -> str:
    regular_tags = [tag for tag in all_tags if tag.hotfix is None]
    if regular_tags:
        return max(regular_tags, key=lambda tag: tag.base_tuple).base_version
    current_year = date.today().year
    return f"v{current_year}.1.0"


def _try_auto_bump(repo: str, all_tags: list[ParsedTag]) -> str | None:
    candidate = _latest_base_version(all_tags)
    if github.is_release_merged(repo, candidate):
        bumped = bump_minor(candidate)
        log.info("  Release %s detected as merged — bumping to %s", candidate, bumped)
        return bumped
    return None


def _safe_auto_bump(repo: str, all_tags: list[ParsedTag]) -> str | None:
    try:
        return _try_auto_bump(repo, all_tags)
    except github.GitHubAPIError:
        return None


def _resolve_base_version(
    repo: str,
    args: Namespace,
    all_tags: list[ParsedTag],
    dry_run: bool,
) -> str | None:
    if args.base_version:
        return args.base_version
    if dry_run:
        return None
    return _safe_auto_bump(repo, all_tags)


def compute_plan(
    args: Namespace,
    repo: str,
    all_tags: list[ParsedTag],
    dry_run: bool,
) -> _PlanResult | None:
    """Compute the next tag and release branch. Returns None on error."""
    try:
        if args.rc_type == "regular":
            base_version = _resolve_base_version(repo, args, all_tags, dry_run)
            next_tag, resolved_bv = compute_next_regular(all_tags, base_version)
        else:
            next_tag, resolved_bv = compute_next_hotfix(all_tags, args.base_version)
    except ValueError as exc:
        log.error("Error: %s", exc)
        return None
    return _PlanResult(
        next_tag=next_tag,
        resolved_bv=resolved_bv,
        release_branch=f"release/{resolved_bv}",
    )
