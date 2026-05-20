"""CLI entry point and workflow orchestration."""

from __future__ import annotations

import sys
from argparse import Namespace

from create_new_rc import github
from create_new_rc._version import (
    bump_minor,
    compute_next_hotfix,
    compute_next_regular,
)
from create_new_rc.cli._args import parse_args


def main() -> None:
    """Entry point for the create-rc CLI."""
    args = parse_args()
    sys.exit(run(args))


def run(args: Namespace) -> int:
    """Orchestrate the release candidate creation workflow.

    Returns 0 on success, 1 on error.
    """
    dry_run: bool = args.dry_run
    prefix = "[DRY RUN] " if dry_run else ""

    # ------------------------------------------------------------------ #
    # Phase 1 — Get repo info
    # ------------------------------------------------------------------ #
    print(f"{prefix}Fetching repository info…")
    try:
        repo = github.get_repo(args.repo)
    except github.GitHubAPIError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(f"{prefix}Repository: {repo}")
    print(f"{prefix}RC type:    {args.rc_type}")
    if args.base_version:
        print(f"{prefix}Base ver:   {args.base_version}")
    print()

    # ------------------------------------------------------------------ #
    # Phase 2 — Fetch tags
    # ------------------------------------------------------------------ #
    print(f"{prefix}Fetching existing tags…")
    try:
        all_tags = github.fetch_all_tags(repo)
    except github.GitHubAPIError as e:
        print(f"Error fetching tags: {e}", file=sys.stderr)
        return 1

    rc_count = len(all_tags)
    print(f"  Found {rc_count} RC tag(s).")
    print()

    # ------------------------------------------------------------------ #
    # Phase 3 — Compute next tag
    # ------------------------------------------------------------------ #
    try:
        if args.rc_type == "regular":
            base_version = args.base_version
            # If not explicitly pinned, check if the current release was merged
            if not base_version and not dry_run:
                try:
                    # Determine the base_version to check
                    regular_tags = [t for t in all_tags if t.hotfix is None]
                    if regular_tags:
                        from .._models import ParsedTag

                        latest = max(regular_tags, key=lambda t: t.base_tuple)
                        candidate_bv = latest.base_version
                    else:
                        from datetime import date

                        year = date.today().year
                        candidate_bv = f"v{year}.1.0"

                    # Check if this release was merged
                    if github.is_release_merged(repo, candidate_bv):
                        old_bv = candidate_bv
                        base_version = bump_minor(candidate_bv)
                        print(
                            f"  Release {old_bv} detected as merged — "
                            f"bumping to {base_version}"
                        )
                except github.GitHubAPIError:
                    # If the check fails, just use the computed base version
                    pass

            next_tag, resolved_base_version = compute_next_regular(
                all_tags, base_version
            )
        else:
            next_tag, resolved_base_version = compute_next_hotfix(
                all_tags, args.base_version
            )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    release_branch = f"release/{resolved_base_version}"

    print(f"{prefix}Next tag:       {next_tag}")
    print(f"{prefix}Release branch: {release_branch}")
    print()

    # ------------------------------------------------------------------ #
    # Phase 4 — Release branch
    # ------------------------------------------------------------------ #
    print(f"{prefix}Checking release branch…")
    try:
        exists = github.branch_exists(repo, release_branch) if not dry_run else False
    except github.GitHubAPIError as e:
        print(f"Error checking branch: {e}", file=sys.stderr)
        return 1

    if exists:
        print(f"  Branch '{release_branch}' already exists.")
        try:
            branch_sha = github.get_branch_sha(repo, release_branch)
            main_sha = github.get_default_branch_sha(repo)
            if branch_sha == main_sha:
                print("  Branch is at same commit as main — adding empty commit.")
                tree_sha = github.get_commit_tree_sha(repo, branch_sha)
                branch_sha = github.create_empty_commit(
                    repo,
                    release_branch,
                    f"chore: initialize {release_branch}",
                    parent_sha=branch_sha,
                    tree_sha=tree_sha,
                )
        except github.GitHubAPIError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    else:
        try:
            if dry_run:
                print(
                    f"  [DRY RUN] Would create branch '{release_branch}' "
                    f"from main."
                )
                print(f"  [DRY RUN] Would add empty commit on '{release_branch}'.")
                branch_sha = "<sha-of-release>"
            else:
                branch_sha = github.get_default_branch_sha(repo)
                tree_sha = github.get_commit_tree_sha(repo, branch_sha)
                github.create_branch(repo, release_branch, branch_sha)
                branch_sha = github.create_empty_commit(
                    repo,
                    release_branch,
                    f"chore: initialize {release_branch}",
                    parent_sha=branch_sha,
                    tree_sha=tree_sha,
                )
        except github.GitHubAPIError as e:
            print(f"Error creating branch: {e}", file=sys.stderr)
            return 1
    print()

    # ------------------------------------------------------------------ #
    # Phase 5 — Create tag
    # ------------------------------------------------------------------ #
    print(f"{prefix}Creating tag…")
    try:
        if dry_run:
            print(f"  [DRY RUN] Would create tag '{next_tag}' at {branch_sha[:8]}.")
        else:
            github.create_tag(repo, next_tag, branch_sha)
    except github.GitHubAPIError as e:
        print(f"Error creating tag: {e}", file=sys.stderr)
        return 1
    print()

    # ------------------------------------------------------------------ #
    # Phase 6 — Create PR
    # ------------------------------------------------------------------ #
    print(f"{prefix}Checking for existing PR…")
    try:
        existing_pr = (
            github.find_open_pr(repo, "main", release_branch) if not dry_run else None
        )
    except github.GitHubAPIError as e:
        print(f"Error checking PRs: {e}", file=sys.stderr)
        return 1

    if existing_pr:
        pr_url = f"https://github.com/{repo}/pull/{existing_pr}"
        print(f"  Open PR already exists: #{existing_pr} — {pr_url}")
    else:
        try:
            if dry_run:
                print(
                    f"  [DRY RUN] Would create PR: "
                    f"'Release {resolved_base_version}' "
                    f"({release_branch} → main)."
                )
            else:
                github.create_pr(repo, resolved_base_version, release_branch)
                # create_pr doesn't return the URL, so we construct it
                print(
                    f"  PR created: https://github.com/{repo}/compare/"
                    f"main...{release_branch}"
                )
        except github.GitHubAPIError as e:
            print(f"Error creating PR: {e}", file=sys.stderr)
            return 1
    print()

    # ------------------------------------------------------------------ #
    # Phase 7 — Summary
    # ------------------------------------------------------------------ #
    print("=" * 50)
    print(f"{'[DRY RUN] ' if dry_run else ''}Summary")
    print("=" * 50)
    print(f"  Repository : {repo}")
    print(f"  Tag        : {next_tag}")
    print(
        f"  Branch     : {release_branch}  "
        f"({'created' if not exists else 'already existed'})"
    )
    if existing_pr:
        print(f"  PR         : #{existing_pr} (already existed)")
    else:
        print(f"  PR         : {'would be created' if dry_run else 'created'}")
    print()
    if dry_run:
        print("No changes were made (--dry-run).")

    return 0
