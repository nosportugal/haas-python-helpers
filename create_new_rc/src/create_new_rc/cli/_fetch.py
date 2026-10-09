"""Fetch repository info and tags from GitHub (phases 1 and 2)."""

from __future__ import annotations

import logging
from argparse import Namespace
from dataclasses import dataclass

from create_new_rc import github
from create_new_rc._models import ParsedTag

log = logging.getLogger(__name__)


@dataclass
class _FetchResult:
    repo: str
    prefix: str
    all_tags: list[ParsedTag]


def _log_repo_header(args: Namespace, prefix: str, repo: str) -> None:
    log.info("%sRepository: %s", prefix, repo)
    log.info("%sRC type:    %s", prefix, args.rc_type)
    if args.base_version:
        log.info("%sBase ver:   %s", prefix, args.base_version)
    log.info("")


def _fetch_repo_info(args: Namespace, prefix: str) -> str | None:
    log.info("%sFetching repository info…", prefix)
    try:
        repo = github.get_repo(args.repo)
    except github.GitHubAPIError as exc:
        log.error("Error: %s", exc)
        return None
    _log_repo_header(args, prefix, repo)
    return repo


def _fetch_tags(repo: str, prefix: str) -> list[ParsedTag] | None:
    log.info("%sFetching existing tags…", prefix)
    try:
        all_tags = github.fetch_all_tags(repo)
    except github.GitHubAPIError as exc:
        log.error("Error fetching tags: %s", exc)
        return None
    log.info("  Found %d RC tag(s).", len(all_tags))
    log.info("")
    return all_tags


def fetch_all(args: Namespace) -> _FetchResult | None:
    """Fetch repo info and all RC tags. Returns None on error."""
    prefix = "[DRY RUN] " if args.dry_run else ""
    repo = _fetch_repo_info(args, prefix)
    if repo is None:
        return None
    all_tags = _fetch_tags(repo, prefix)
    if all_tags is None:
        return None
    return _FetchResult(repo=repo, prefix=prefix, all_tags=all_tags)
