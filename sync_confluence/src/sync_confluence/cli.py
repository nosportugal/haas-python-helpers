"""Sync a docs/ directory tree to Confluence Cloud as nested pages.

Mirrors the folder structure under a configured parent page.
README.md files become section parent pages; other .md files become
leaf pages.  Markdown is converted to Confluence Storage Format with
code macros, optional Mermaid macro support, and relative-link
rewriting to GitHub URLs.

Configuration
-------------
Every required value can be provided as a CLI argument **or** an
environment variable.  CLI arguments take precedence.

    CONFLUENCE_URL             Base URL (e.g. https://acme.atlassian.net)
    CONFLUENCE_EMAIL           Atlassian account email
    CONFLUENCE_API_TOKEN       API token from id.atlassian.com
    CONFLUENCE_SPACE_KEY       Target space key
    CONFLUENCE_PARENT_PAGE_ID  Numeric ID of the pre-existing parent page
    CONFLUENCE_ROOT_TITLE      Title for the root page (optional)
    CONFLUENCE_MERMAID_MACRO   Mermaid macro name if plugin installed (optional)
    CONFLUENCE_MANAGED_BY      Label to mark pages owned by this automation;
                              auto-derived from the git repo name if unset (optional)
    DOCS_DIR                   Path to docs directory (default: docs)
    GITHUB_REF_NAME            Git ref for link construction (default: main)
    LOG_LEVEL                  Logging verbosity (default: INFO)

Usage
-----
  # Dry run — preview without making changes (reads Confluence to check labels):
  python sync_confluence --dry-run \\
      --url https://acme.atlassian.net \\
      --email user@acme.com --token xxxxxxxxxxx \\
      --space DOCS --parent-id 12345

  # Live sync (orphan cleanup runs automatically, guarded by managed-by label):
  python sync_confluence \\
      --url https://acme.atlassian.net \\
      --email user@acme.com --token xxxxxxxxxxx \\
      --space DOCS --parent-id 12345
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

from atlassian import Confluence
from .confluence import (
    _find_folder_under_parent,
    _find_page_under_parent,
    delete_orphans,
    upsert_folder,
)
from .traversal import sync_directory, sync_files

log = logging.getLogger(__name__)


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read an environment variable, returning *default* if unset or empty."""
    value = os.environ.get(name, "")
    return value if value else default


def _detect_repo_url() -> Optional[str]:
    """Auto-detect the repository's HTTPS URL from the environment or git remote.

    Resolution order:
    1. ``GITHUB_SERVER_URL`` + ``GITHUB_REPOSITORY`` (set in GitHub Actions).
    2. ``git remote get-url origin``, normalised to HTTPS.

    Returns ``None`` if the URL cannot be determined.
    """
    server = os.environ.get("GITHUB_SERVER_URL", "").rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if server and repo:
        return f"{server}/{repo}"

    try:
        remote = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        # Normalise SSH remote (git@github.com:org/repo.git) to HTTPS
        if remote.startswith("git@"):
            remote = re.sub(r"^git@([^:]+):(.+?)(?:\.git)?$", r"https://\1/\2", remote)
        else:
            remote = remote.rstrip("/").removesuffix(".git")
        return remote or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _label_from_repo_url(repo_url: str) -> Optional[str]:
    """Derive a ``managed-by-<repo>`` Confluence label from a repository URL."""
    repo_name = repo_url.rstrip("/").rsplit("/", 1)[-1]
    sanitised = re.sub(r"[^a-z0-9-]+", "-", repo_name.lower()).strip("-")
    return f"managed-by-{sanitised}" if sanitised else None


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Sync a docs/ tree to Confluence Cloud.",
    )
    p.add_argument(
        "--url",
        default=_env("CONFLUENCE_URL"),
        help="Confluence base URL (env: CONFLUENCE_URL).",
    )
    p.add_argument(
        "--email",
        default=_env("CONFLUENCE_EMAIL"),
        help="Atlassian account email (env: CONFLUENCE_EMAIL).",
    )
    p.add_argument(
        "--token",
        default=_env("CONFLUENCE_API_TOKEN"),
        help="Atlassian API token (env: CONFLUENCE_API_TOKEN).",
    )
    p.add_argument(
        "--space",
        default=_env("CONFLUENCE_SPACE_KEY"),
        help="Confluence space key (env: CONFLUENCE_SPACE_KEY).",
    )
    p.add_argument(
        "--parent-id",
        default=_env("CONFLUENCE_PARENT_PAGE_ID"),
        help="Numeric ID of the parent page (env: CONFLUENCE_PARENT_PAGE_ID).",
    )
    p.add_argument(
        "--docs-dir",
        default=_env("DOCS_DIR"),
        help=(
            "Path to the docs directory (env: DOCS_DIR). "
            "Auto-detected from common names (docs/, documentation/, doc/) "
            "when not set. Mutually exclusive with --docs-files."
        ),
    )
    p.add_argument(
        "--docs-files",
        nargs="+",
        metavar="FILE",
        help=(
            "One or more Markdown files to sync as leaf pages directly under "
            "the parent. Mutually exclusive with --docs-dir."
        ),
    )
    p.add_argument(
        "--root-title",
        default=_env("CONFLUENCE_ROOT_TITLE"),
        help=(
            "Title for the root page.  Defaults to the first H1 heading "
            "in docs/README.md (env: CONFLUENCE_ROOT_TITLE)."
        ),
    )
    p.add_argument(
        "--git-ref",
        default=_env("GITHUB_REF_NAME", "main"),
        help="Git ref used in GitHub link construction (env: GITHUB_REF_NAME).",
    )
    p.add_argument(
        "--mermaid-macro",
        default=_env("CONFLUENCE_MERMAID_MACRO"),
        help=(
            "Confluence macro name for Mermaid diagrams.  "
            "Omit to render Mermaid as a code block "
            "(env: CONFLUENCE_MERMAID_MACRO)."
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview pages that would be created/updated/deleted.",
    )
    p.add_argument(
        "--no-root",
        action="store_true",
        help=(
            "Sync all docs directly under --parent-id without creating an "
            "intermediate root page from docs/README.md. "
            "Mutually exclusive with --root-parent and --root-title."
        ),
    )
    p.add_argument(
        "--root-parent",
        default=_env("CONFLUENCE_ROOT_PARENT"),
        help=(
            "Title of a container page to find or create under --parent-id. "
            "All docs are synced directly under this container. "
            "Mutually exclusive with --no-root and --root-title "
            "(env: CONFLUENCE_ROOT_PARENT)."
        ),
    )
    p.add_argument(
        "--managed-by",
        default=_env("CONFLUENCE_MANAGED_BY"),
        help=(
            "Confluence label applied to every page created or updated by this sync. "
            "Only pages carrying this label are eligible for orphan removal, "
            "preventing accidental deletion of unrelated pages. "
            "Auto-derived from the git repository name when not set "
            "(e.g. 'managed-by-a3-e2e'). "
            "(env: CONFLUENCE_MANAGED_BY)"
        ),
    )
    p.add_argument(
        "--log-level",
        default=_env("LOG_LEVEL", "INFO"),
        help="Logging verbosity (env: LOG_LEVEL, default: INFO).",
    )
    return p.parse_args(argv)


def validate_args(args: argparse.Namespace) -> None:
    """Exit with code 2 if any required argument is missing."""
    missing = []
    for attr, label in [
        ("url", "--url / CONFLUENCE_URL"),
        ("email", "--email / CONFLUENCE_EMAIL"),
        ("token", "--token / CONFLUENCE_API_TOKEN"),
        ("space", "--space / CONFLUENCE_SPACE_KEY"),
        ("parent_id", "--parent-id / CONFLUENCE_PARENT_PAGE_ID"),
    ]:
        if not getattr(args, attr, None):
            missing.append(label)
    if missing:
        log.error("Missing required configuration: %s", ", ".join(missing))
        sys.exit(2)

    root_opts = [
        o for o in ("no_root", "root_parent", "root_title") if getattr(args, o, None)
    ]
    if len(root_opts) > 1:
        log.error(
            "--no-root, --root-parent, and --root-title are mutually exclusive; "
            "provide at most one."
        )
        sys.exit(2)

    if args.docs_dir and getattr(args, "docs_files", None):
        log.error("--docs-dir and --docs-files are mutually exclusive.")
        sys.exit(2)


_DOCS_CANDIDATES = ("docs", "documentation", "doc")


def run(args: argparse.Namespace) -> int:
    """Execute the sync.  Returns an exit code (0 = success, 1 = error)."""
    mode = "DRY-RUN" if args.dry_run else "LIVE"
    log.info("Confluence: %s", args.url)
    log.info("Space: %s  |  Parent page: %s", args.space, args.parent_id)

    # Determine sync mode and docs root
    docs_files: list[Path] = []
    sync_mode = "directory"
    if getattr(args, "docs_files", None):
        docs_files = [Path(f) for f in args.docs_files]
        docs_root = Path.cwd()
        sync_mode = "files"
        log.info("Syncing %d file(s)  |  Mode: %s", len(docs_files), mode)
    elif args.docs_dir:
        docs_root = Path(args.docs_dir)
        if not docs_root.is_dir():
            log.error("Docs directory not found: %s", docs_root)
            return 1
        log.info("Docs dir: %s  |  Mode: %s", docs_root, mode)
    else:
        for _candidate in _DOCS_CANDIDATES:
            _path = Path(_candidate)
            if _path.is_dir():
                docs_root = _path
                log.info(
                    "Auto-detected docs directory: %s/  |  Mode: %s",
                    docs_root,
                    mode,
                )
                break
        else:
            log.error(
                "Could not find a docs directory. Pass --docs-dir or create one of: %s",
                ", ".join(f"{c}/" for c in _DOCS_CANDIDATES),
            )
            return 1

    # Auto-detect repository URL for link rewriting and managed-by label
    repo_url = _detect_repo_url()
    if not repo_url:
        log.warning(
            "Could not detect repository URL: not inside a git repository "
            "and GITHUB_SERVER_URL / GITHUB_REPOSITORY are not set. "
            "Relative links will not be rewritten and managed-by label "
            "cannot be auto-derived."
        )

    # Resolve ownership label (explicit > auto-derived from git > None)
    if args.managed_by:
        managed_by_label: Optional[str] = args.managed_by
        log.info("Managed-by label: %s (explicit)", managed_by_label)
    elif repo_url:
        managed_by_label = _label_from_repo_url(repo_url)
        log.info(
            "Managed-by label: %s (derived from repository name)",
            managed_by_label,
        )
    else:
        managed_by_label = None
        log.warning(
            "Orphan cleanup will target ALL pages under the parent "
            "regardless of origin."
        )

    confluence = Confluence(
        url=args.url,
        username=args.email,
        password=args.token,
        cloud=True,
    )
    user_details = confluence.get("rest/api/user/current")
    if not user_details or "accountId" not in user_details:
        log.error(
            "Could not resolve accountId for '%s'. "
            "Edit restrictions cannot be applied.",
            args.email,
        )
        return 1
    if args.dry_run:
        restrict_edits_to: Optional[str] = "DRY-RUN"
        log.info("[DRY-RUN] Would apply edit restrictions (authenticated user)")
    else:
        restrict_edits_to = user_details["accountId"]
        log.info("Edit restrictions enabled for accountId=%s", restrict_edits_to)

    # Determine effective parent, sync depth, and readme_as_parent mode
    effective_parent_id = args.parent_id
    readme_as_parent = True
    sync_depth = 0

    if args.no_root:
        readme_as_parent = False
    elif args.root_parent:
        log.info(
            "Searching for root parent '%s' under parent %s",
            args.root_parent,
            args.parent_id,
        )
        if args.dry_run:
            log.info(
                "Would find or create root parent '%s' under parent %s",
                args.root_parent,
                args.parent_id,
            )
            effective_parent_id = "DRY-RUN"
        else:
            # Try folder first — avoids spurious ERROR from atlassian lib
            existing: Optional[dict] = _find_folder_under_parent(
                confluence, args.space, args.root_parent, args.parent_id
            )
            if existing is None:
                existing = _find_page_under_parent(
                    confluence, args.space, args.root_parent, args.parent_id
                )
            if existing:
                effective_parent_id = existing["id"]
                log.info(
                    "Found root parent '%s' (id=%s)",
                    args.root_parent,
                    effective_parent_id,
                )
            else:
                # Always create as a Confluence Folder when not found
                folder_id, _ = upsert_folder(
                    confluence,
                    args.space,
                    args.parent_id,
                    args.root_parent,
                    False,
                    managed_by_label,
                )
                effective_parent_id = folder_id
                log.info(
                    "Created root parent '%s' (id=%s)",
                    args.root_parent,
                    effective_parent_id,
                )
        readme_as_parent = False
        sync_depth = 1

    # Sync the docs tree
    if sync_mode == "files":
        page_map, expected_titles, expected_paths, skipped, stats = sync_files(
            confluence,
            args.space,
            effective_parent_id,
            docs_files,
            docs_root,
            mermaid_macro=args.mermaid_macro,
            repo_url=repo_url,
            git_ref=args.git_ref,
            dry_run=args.dry_run,
            depth=sync_depth,
            managed_by_label=managed_by_label,
            restrict_edits_to=restrict_edits_to,
        )
    else:
        page_map, expected_titles, expected_paths, skipped, stats = sync_directory(
            confluence,
            args.space,
            effective_parent_id,
            docs_root,
            docs_root,
            root_title=args.root_title,
            mermaid_macro=args.mermaid_macro,
            repo_url=repo_url,
            git_ref=args.git_ref,
            dry_run=args.dry_run,
            depth=sync_depth,
            readme_as_parent=readme_as_parent,
            managed_by_label=managed_by_label,
            restrict_edits_to=restrict_edits_to,
        )

    # Orphan cleanup — runs unconditionally; managed_by_label is the safety guard.
    deleted = 0
    if effective_parent_id == "DRY-RUN":
        log.info("[DRY-RUN] Skipping orphan check — parent page does not exist yet")
    else:
        if not managed_by_label:
            log.warning(
                "No managed-by label is set — orphan cleanup will target ALL "
                "unmatched pages under the parent regardless of origin."
            )
        deleted = delete_orphans(
            confluence,
            effective_parent_id,
            expected_titles,
            args.dry_run,
            managed_by_label,
            expected_paths,
        )

    log.info(
        "Sync complete — created: %d, updated: %d, unchanged: %d, "
        "skipped: %d, orphans deleted: %d",
        stats["created"],
        stats["updated"],
        stats["unchanged"],
        stats["skipped"],
        deleted,
    )
    if skipped:
        log.warning(
            "%d page(s) skipped due to title collisions with unrelated "
            "Confluence pages — rename the source files to resolve: %s",
            len(skipped),
            ", ".join(skipped),
        )

    return 1 if skipped else 0


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s: %(message)s",
    )
    # Suppress the atlassian-python-api library's own INFO/DEBUG request logs
    # (e.g. "rest/api/content/{id}/child/page") — they add noise without value.
    logging.getLogger("atlassian").setLevel(logging.WARNING)
    validate_args(args)
    sys.exit(run(args))
