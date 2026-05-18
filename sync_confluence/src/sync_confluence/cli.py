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
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from atlassian import Confluence

from sync_confluence.confluence import (
    DeleteOrphansRequest,
    FolderUpsertRequest,
    delete_orphans,
    upsert_folder,
)
from sync_confluence.confluence._lookup import (
    _find_folder_under_parent,
    _find_page_under_parent,
)
from sync_confluence.traversal import (
    SyncContext,
    SyncResult,
    sync_directory,
    sync_files,
)

log = logging.getLogger(__name__)


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read an environment variable, returning *default* if unset or empty."""
    env_value = os.environ.get(name, "")
    return env_value if env_value else default


def _get_git_remote_url() -> Optional[str]:
    """Return the normalised HTTPS URL from ``git remote get-url origin``."""
    remote = subprocess.check_output(
        ["git", "remote", "get-url", "origin"],
        stderr=subprocess.DEVNULL,
        text=True,
    ).strip()
    if remote.startswith("git@"):
        remote = re.sub(r"^git@([^:]+):(.+?)(?:\.git)?$", r"https://\1/\2", remote)
    else:
        remote = remote.rstrip("/").removesuffix(".git")
    return remote or None


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
        return _get_git_remote_url()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _label_from_repo_url(repo_url: str) -> Optional[str]:
    """Derive a ``managed-by-<repo>`` Confluence label from a repository URL."""
    repo_name = repo_url.rstrip("/").rsplit("/", 1)[-1]
    sanitised = re.sub(r"[^a-z0-9-]+", "-", repo_name.lower()).strip("-")
    return f"managed-by-{sanitised}" if sanitised else None


def _add_connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--url",
        default=_env("CONFLUENCE_URL"),
        help="Confluence base URL (env: CONFLUENCE_URL).",
    )
    parser.add_argument(
        "--email",
        default=_env("CONFLUENCE_EMAIL"),
        help="Atlassian account email (env: CONFLUENCE_EMAIL).",
    )
    parser.add_argument(
        "--token",
        default=_env("CONFLUENCE_API_TOKEN"),
        help="Atlassian API token (env: CONFLUENCE_API_TOKEN).",
    )
    parser.add_argument(
        "--space",
        default=_env("CONFLUENCE_SPACE_KEY"),
        help="Confluence space key (env: CONFLUENCE_SPACE_KEY).",
    )
    parser.add_argument(
        "--parent-id",
        default=_env("CONFLUENCE_PARENT_PAGE_ID"),
        help="Numeric ID of the parent page (env: CONFLUENCE_PARENT_PAGE_ID).",
    )


def _add_docs_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--docs-dir",
        default=_env("DOCS_DIR"),
        help=(
            "Path to the docs directory (env: DOCS_DIR). "
            "Auto-detected from common names (docs/, documentation/, doc/) "
            "when not set. Mutually exclusive with --docs-files."
        ),
    )
    parser.add_argument(
        "--docs-files",
        nargs="+",
        metavar="FILE",
        help=(
            "One or more Markdown files to sync as leaf pages directly under "
            "the parent. Mutually exclusive with --docs-dir."
        ),
    )
    parser.add_argument(
        "--root-title",
        default=_env("CONFLUENCE_ROOT_TITLE"),
        help=(
            "Title for the root page.  Defaults to the first H1 heading "
            "in docs/README.md (env: CONFLUENCE_ROOT_TITLE)."
        ),
    )


def _add_sync_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--git-ref",
        default=_env("GITHUB_REF_NAME", "main"),
        help="Git ref used in GitHub link construction (env: GITHUB_REF_NAME).",
    )
    parser.add_argument(
        "--mermaid-macro",
        default=_env("CONFLUENCE_MERMAID_MACRO"),
        help=(
            "Confluence macro name for Mermaid diagrams.  "
            "Omit to render Mermaid as a code block "
            "(env: CONFLUENCE_MERMAID_MACRO)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview pages that would be created/updated/deleted.",
    )
    parser.add_argument(
        "--no-root",
        action="store_true",
        help=(
            "Sync all docs directly under --parent-id without creating an "
            "intermediate root page from docs/README.md. "
            "Mutually exclusive with --root-parent and --root-title."
        ),
    )
    parser.add_argument(
        "--root-parent",
        default=_env("CONFLUENCE_ROOT_PARENT"),
        help=(
            "Title of a container page to find or create under --parent-id. "
            "All docs are synced directly under this container. "
            "Mutually exclusive with --no-root and --root-title "
            "(env: CONFLUENCE_ROOT_PARENT)."
        ),
    )


def _add_meta_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
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
    parser.add_argument(
        "--log-level",
        default=_env("LOG_LEVEL", "INFO"),
        help="Logging verbosity (env: LOG_LEVEL, default: INFO).",
    )


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync a docs/ tree to Confluence Cloud.",
    )
    _add_connection_args(parser)
    _add_docs_args(parser)
    _add_sync_args(parser)
    _add_meta_args(parser)
    return parser.parse_args(argv)


def validate_args(args: argparse.Namespace) -> None:
    """Exit with code 2 if any required argument is missing."""
    missing = []
    for attr, label in (
        ("url", "--url / CONFLUENCE_URL"),
        ("email", "--email / CONFLUENCE_EMAIL"),
        ("token", "--token / CONFLUENCE_API_TOKEN"),
        ("space", "--space / CONFLUENCE_SPACE_KEY"),
        ("parent_id", "--parent-id / CONFLUENCE_PARENT_PAGE_ID"),
    ):
        if not getattr(args, attr, None):
            missing.append(label)
    if missing:
        log.error("Missing required configuration: %s", ", ".join(missing))
        sys.exit(2)

    root_opts = [
        opt_name
        for opt_name in ("no_root", "root_parent", "root_title")
        if getattr(args, opt_name, None)
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
_DRY_RUN_ID = "DRY-RUN"
_SYNC_MODE_DIR = "directory"
_SYNC_MODE_FILES = "files"


def _resolve_docs_root(
    args: argparse.Namespace,
) -> tuple[Optional[Path], str, list[Path]]:
    """Determine docs_root, sync_mode and docs_files from args.

    Returns ``(docs_root, sync_mode, docs_files)`` where *docs_root* is
    ``None`` when an error message has already been logged and the caller
    should return 1.
    """
    if getattr(args, "docs_files", None):
        docs_files = [Path(docs_file_path) for docs_file_path in args.docs_files]
        return Path.cwd(), _SYNC_MODE_FILES, docs_files
    if args.docs_dir:
        docs_root = Path(args.docs_dir)
        if not docs_root.is_dir():
            log.error("Docs directory not found: %s", docs_root)
            return None, _SYNC_MODE_DIR, []
        return docs_root, _SYNC_MODE_DIR, []
    for candidate in _DOCS_CANDIDATES:
        candidate_path = Path(candidate)
        if candidate_path.is_dir():
            return candidate_path, _SYNC_MODE_DIR, []
    log.error(
        "Could not find a docs directory. Pass --docs-dir or create one of: %s",
        ", ".join(f"{dir_name}/" for dir_name in _DOCS_CANDIDATES),
    )
    return None, _SYNC_MODE_DIR, []


def _resolve_managed_by_label(
    args: argparse.Namespace, repo_url: Optional[str]
) -> Optional[str]:
    """Resolve the managed-by Confluence label from explicit arg or repo URL."""
    if args.managed_by:
        managed_by: Optional[str] = args.managed_by
        log.info("Managed-by label: %s (explicit)", managed_by)
        return managed_by
    if repo_url:
        managed_by = _label_from_repo_url(repo_url)
        log.info("Managed-by label: %s (derived from repository name)", managed_by)
        return managed_by
    log.warning(
        "Orphan cleanup will target ALL pages under the parent regardless of origin."
    )
    return None


@dataclass
class _DocsInfo:
    """Resolved docs location and mode."""

    root: Path
    mode: str
    files: list[Path]


@dataclass
class _AuthInfo:
    """Confluence connection plus repository/label metadata."""

    confluence: Confluence
    repo_url: Optional[str]
    managed_by_label: Optional[str]
    restrict_edits_to: str


@dataclass
class _SyncPlan:
    """Where and how to walk the docs tree."""

    parent_id: str
    readme_as_parent: bool
    depth: int


def _log_sync_target(
    sync_mode: str, docs_files: list[Path], docs_root: Path, dry_run: bool
) -> None:
    mode_label = _DRY_RUN_ID if dry_run else "LIVE"
    if sync_mode == _SYNC_MODE_FILES:
        log.info("Syncing %d file(s)  |  Mode: %s", len(docs_files), mode_label)
    else:
        log.info("Docs dir: %s  |  Mode: %s", docs_root, mode_label)


def _resolve_docs(args: argparse.Namespace) -> Optional[_DocsInfo]:
    """Resolve docs location, log the sync target, or return ``None`` on error."""
    docs_root, sync_mode, docs_files = _resolve_docs_root(args)
    if docs_root is None:
        return None
    _log_sync_target(sync_mode, docs_files, docs_root, args.dry_run)
    return _DocsInfo(root=docs_root, mode=sync_mode, files=docs_files)


def _connect_confluence(args: argparse.Namespace) -> Confluence:
    return Confluence(
        url=args.url, username=args.email, password=args.token, cloud=True
    )


def _resolve_restrict_edits_to(
    confluence: Confluence, args: argparse.Namespace
) -> Optional[str]:
    """Return the accountId to restrict edits to (``"DRY-RUN"`` in dry-run)."""
    user_details = confluence.get("rest/api/user/current")
    if not user_details or "accountId" not in user_details:
        log.error(
            "Could not resolve accountId for '%s'. "
            "Edit restrictions cannot be applied.",
            args.email,
        )
        return None
    if args.dry_run:
        log.info("[DRY-RUN] Would apply edit restrictions (authenticated user)")
        return _DRY_RUN_ID
    account_id = user_details["accountId"]
    log.info("Edit restrictions enabled for accountId=%s", account_id)
    return account_id


def _prepare_auth(args: argparse.Namespace) -> Optional[_AuthInfo]:
    """Detect repo URL, derive label, connect, resolve account id."""
    repo_url = _detect_repo_url()
    if not repo_url:
        log.warning(
            "Could not detect repository URL: not inside a git repository "
            "and GITHUB_SERVER_URL / GITHUB_REPOSITORY are not set. "
            "Relative links will not be rewritten and managed-by label "
            "cannot be auto-derived."
        )
    managed_by_label = _resolve_managed_by_label(args, repo_url)
    confluence = _connect_confluence(args)
    restrict_edits_to = _resolve_restrict_edits_to(confluence, args)
    if restrict_edits_to is None:
        return None
    return _AuthInfo(
        confluence=confluence,
        repo_url=repo_url,
        managed_by_label=managed_by_label,
        restrict_edits_to=restrict_edits_to,
    )


def _find_or_create_root_parent(
    confluence: Confluence, args: argparse.Namespace, managed_by_label: Optional[str]
) -> str:
    existing = _find_folder_under_parent(
        confluence, args.space, args.root_parent, args.parent_id
    )
    if existing is None:
        existing = _find_page_under_parent(
            confluence, args.space, args.root_parent, args.parent_id
        )
    if existing:
        log.info("Found root parent '%s' (id=%s)", args.root_parent, existing["id"])
        return existing["id"]
    folder_id, _ = upsert_folder(
        confluence,
        FolderUpsertRequest(
            space_key=args.space,
            parent_id=args.parent_id,
            title=args.root_parent,
            dry_run=False,
            managed_by_label=managed_by_label,
        ),
    )
    log.info("Created root parent '%s' (id=%s)", args.root_parent, folder_id)
    return folder_id


def _resolve_root_parent(
    confluence: Confluence, args: argparse.Namespace, managed_by_label: Optional[str]
) -> str:
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
        return _DRY_RUN_ID
    return _find_or_create_root_parent(confluence, args, managed_by_label)


def _resolve_sync_plan(
    confluence: Confluence, args: argparse.Namespace, managed_by_label: Optional[str]
) -> _SyncPlan:
    """Determine the parent page, depth, and README handling for the walk."""
    if args.no_root:
        return _SyncPlan(parent_id=args.parent_id, readme_as_parent=False, depth=0)
    if not args.root_parent:
        return _SyncPlan(parent_id=args.parent_id, readme_as_parent=True, depth=0)
    parent_id = _resolve_root_parent(confluence, args, managed_by_label)
    return _SyncPlan(parent_id=parent_id, readme_as_parent=False, depth=1)


def _build_sync_context(
    args: argparse.Namespace, docs: _DocsInfo, auth: _AuthInfo
) -> SyncContext:
    return SyncContext(
        confluence=auth.confluence,
        space_key=args.space,
        docs_root=docs.root,
        root_title=args.root_title,
        mermaid_macro=args.mermaid_macro,
        repo_url=auth.repo_url,
        git_ref=args.git_ref,
        dry_run=args.dry_run,
        managed_by_label=auth.managed_by_label,
        restrict_edits_to=auth.restrict_edits_to,
    )


def _dispatch_sync(
    args: argparse.Namespace, docs: _DocsInfo, auth: _AuthInfo, plan: _SyncPlan
) -> SyncResult:
    ctx = _build_sync_context(args, docs, auth)
    if docs.mode == _SYNC_MODE_FILES:
        return sync_files(ctx, plan.parent_id, docs.files, depth=plan.depth)
    return sync_directory(
        ctx,
        plan.parent_id,
        docs.root,
        depth=plan.depth,
        readme_as_parent=plan.readme_as_parent,
    )


def _run_orphan_cleanup(
    auth: _AuthInfo, parent_id: str, sync_result: SyncResult, dry_run: bool
) -> int:
    if parent_id == _DRY_RUN_ID:
        log.info("[DRY-RUN] Skipping orphan check — parent page does not exist yet")
        return 0
    if not auth.managed_by_label:
        log.warning(
            "No managed-by label is set — orphan cleanup will target ALL "
            "unmatched pages under the parent regardless of origin."
        )
    request = DeleteOrphansRequest(
        root_page_id=parent_id,
        expected_titles=sync_result.expected_titles,
        dry_run=dry_run,
        managed_by_label=auth.managed_by_label,
        expected_paths=sync_result.expected_paths,
    )
    return delete_orphans(auth.confluence, request)


def _log_sync_summary(sync_result: SyncResult, deleted: int) -> None:
    log.info(
        "Sync complete — created: %d, updated: %d, unchanged: %d, "
        "skipped: %d, orphans deleted: %d",
        sync_result.stats["created"],
        sync_result.stats["updated"],
        sync_result.stats["unchanged"],
        sync_result.stats["skipped"],
        deleted,
    )
    if sync_result.skipped:
        log.warning(
            "%d page(s) skipped due to title collisions with unrelated "
            "Confluence pages — rename the source files to resolve: %s",
            len(sync_result.skipped),
            ", ".join(sync_result.skipped),
        )


def _finalise_run(
    sync_result: SyncResult,
    auth: _AuthInfo,
    plan: _SyncPlan,
    args: argparse.Namespace,
) -> None:
    deleted = _run_orphan_cleanup(auth, plan.parent_id, sync_result, args.dry_run)
    _log_sync_summary(sync_result, deleted)


def _log_run_header(args: argparse.Namespace) -> None:
    log.info("Confluence: %s", args.url)
    log.info("Space: %s  |  Parent page: %s", args.space, args.parent_id)


def run(args: argparse.Namespace) -> int:
    """Execute the sync.  Returns an exit code (0 = success, 1 = error)."""
    _log_run_header(args)
    docs = _resolve_docs(args)
    if docs is None:
        return 1
    auth = _prepare_auth(args)
    if auth is None:
        return 1
    plan = _resolve_sync_plan(auth.confluence, args, auth.managed_by_label)
    sync_result = _dispatch_sync(args, docs, auth, plan)
    _finalise_run(sync_result, auth, plan, args)
    return 1 if sync_result.skipped else 0


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
