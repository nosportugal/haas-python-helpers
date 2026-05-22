"""CLI entry point and workflow orchestration."""

from __future__ import annotations

import logging
import sys
from argparse import Namespace

from create_new_rc.cli._args import parse_args
from create_new_rc.cli._branch import _BranchResult, prepare_branch
from create_new_rc.cli._compute import _PlanResult, compute_plan
from create_new_rc.cli._fetch import _FetchResult, fetch_all
from create_new_rc.cli._publish import ensure_pr, publish_tag
from create_new_rc.cli._summary import print_summary

log = logging.getLogger(__name__)


def _finalise(
    fetch: _FetchResult,
    plan: _PlanResult,
    branch: _BranchResult,
    dry_run: bool,
) -> int:
    if publish_tag(fetch.repo, plan, branch.sha, dry_run, fetch.prefix):
        return 1
    if ensure_pr(fetch.repo, plan, dry_run, fetch.prefix):
        return 1
    print_summary(
        fetch.repo, plan.next_tag, plan.release_branch, branch.existed, dry_run
    )
    return 0


def run(args: Namespace) -> int:
    """Orchestrate the release candidate creation workflow."""
    fetch = fetch_all(args)
    if fetch is None:
        return 1
    plan = compute_plan(args, fetch.repo, fetch.all_tags, args.dry_run)
    if plan is None:
        return 1
    branch = prepare_branch(fetch.repo, plan.release_branch, args.dry_run, fetch.prefix)
    if branch is None:
        return 1
    return _finalise(fetch, plan, branch, args.dry_run)


def main() -> None:
    """Entry point for the create-rc CLI."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args()
    sys.exit(run(args))
