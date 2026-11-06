"""Repository URL detection and managed-by label resolution helpers."""

from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
from typing import Optional

log = logging.getLogger(__name__)


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


def detect_repo_url() -> Optional[str]:
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


def managed_by_label_from_repo_url(repo_url: str) -> Optional[str]:
    """Derive a ``managed-by-<repo>`` Confluence label from a repository URL."""
    repo_name = repo_url.rstrip("/").rsplit("/", 1)[-1]
    sanitised = re.sub(r"[^a-z0-9-]+", "-", repo_name.lower()).strip("-")
    return f"managed-by-{sanitised}" if sanitised else None


def resolve_managed_by_label(
    args: argparse.Namespace, repo_url: Optional[str]
) -> Optional[str]:
    """Resolve the managed-by Confluence label from explicit arg or repo URL."""
    if args.managed_by:
        managed_by: Optional[str] = args.managed_by
        log.info("Managed-by label: %s (explicit)", managed_by)
        return managed_by
    if repo_url:
        managed_by = managed_by_label_from_repo_url(repo_url)
        log.info("Managed-by label: %s (derived from repository name)", managed_by)
        return managed_by
    log.warning(
        "Orphan cleanup will target ALL pages under the parent regardless of origin."
    )
    return None
