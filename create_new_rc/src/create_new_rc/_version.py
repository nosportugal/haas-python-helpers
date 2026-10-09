"""Pure version computation logic."""

from __future__ import annotations

import re
from datetime import date

from create_new_rc._models import ParsedTag


def latest_base_version_from_tags(tags: list[ParsedTag]) -> str | None:
    """Return the base_version string of the highest versioned tag.

    Args:
        tags: A list of ParsedTag objects.

    Returns:
        The base version string of the maximum tag by semantic version,
        or None if tags is empty.
    """
    if not tags:
        return None
    latest = max(tags, key=lambda tag: tag.base_tuple)
    return latest.base_version


def parse_base_version(version_str: str) -> tuple[int, int, int]:
    """Parse a base version string into (year, minor, patch).

    Args:
        version_str: A version string like 'v2026.2.0'.

    Returns:
        A 3-tuple of (year, minor, patch) as integers.

    Raises:
        ValueError: If the version string does not match the expected format.
    """
    match_result = re.match(r"^v(\d+)\.(\d+)\.(\d+)$", version_str)
    if not match_result:
        msg = (
            f"Invalid base version '{version_str}'. "
            "Expected format: vYYYY.MINOR.PATCH"
        )
        raise ValueError(msg)
    year_str = match_result.group(1)
    minor_str = match_result.group(2)
    patch_str = match_result.group(3)
    return int(year_str), int(minor_str), int(patch_str)


def bump_minor(base_version: str) -> str:
    """Increment the minor component of a base version.

    Args:
        base_version: A version string like 'v2026.1.0'.

    Returns:
        The bumped version string, e.g., 'v2026.2.0'.
    """
    year, minor, patch = parse_base_version(base_version)
    bumped_minor = minor + 1
    return f"v{year}.{bumped_minor}.0"


def _resolve_base_version(
    tags: list[ParsedTag],
    base_version: str | None,
    include_hotfix: bool,
) -> str:
    """Resolve which base version to use for RC tags.

    Helper for compute_next_regular and compute_next_hotfix to reduce
    complexity.

    Args:
        tags: All parsed RC tags from the repository.
        base_version: An explicit base version, or None to auto-detect.
        include_hotfix: If True, consider hotfix tags; if False, only regular tags.

    Returns:
        The resolved base version string.
    """
    if base_version:
        return base_version
    # Filter tags based on whether we want hotfix tags
    if include_hotfix:
        candidate_tags = [tag for tag in tags if tag.hotfix is not None]
    else:
        candidate_tags = [tag for tag in tags if tag.hotfix is None]
    if candidate_tags:
        latest_tag = max(candidate_tags, key=lambda tag: tag.base_tuple)
        return latest_tag.base_version
    if tags and include_hotfix:
        # Fall back to the latest base version from any tag
        latest_bv = latest_base_version_from_tags(tags)
        if latest_bv is None:
            msg = "Unexpected: tags list is non-empty but no base version found"
            raise ValueError(msg)
        return latest_bv
    # No tags at all — default to current year, 1.0
    current_year = date.today().year
    return f"v{current_year}.1.0"


def compute_next_regular(
    tags: list[ParsedTag],
    base_version: str | None,
) -> tuple[str, str]:
    """Compute the next regular RC tag and base version.

    This function is pure; it does NOT check whether a release branch
    has been merged. That check is the responsibility of the caller.

    Args:
        tags: All parsed RC tags from the repository.
        base_version: An explicit base version (e.g., 'v2026.2.0'), or None
            to auto-detect from the latest regular tag.

    Returns:
        A tuple (next_tag, resolved_base_version). For example:
        - ('v2026.2.0-rc3', 'v2026.2.0')
        - ('v2026.1.0-rc0', 'v2026.1.0')
    """
    regular_tags = [tag for tag in tags if tag.hotfix is None]
    resolved_base_version = _resolve_base_version(tags, base_version, False)
    version_tuple = parse_base_version(resolved_base_version)

    # Find the highest RC for this base version
    matching = [
        tag for tag in regular_tags
        if (tag.year, tag.minor, tag.patch) == version_tuple
    ]
    next_rc = max((tag.rc for tag in matching), default=-1) + 1
    return f"{resolved_base_version}-rc{next_rc}", resolved_base_version


def compute_next_hotfix(
    tags: list[ParsedTag],
    base_version: str | None,
) -> tuple[str, str]:
    """Compute the next hotfix RC tag and base version.

    Args:
        tags: All parsed RC tags from the repository.
        base_version: An explicit base version (e.g., 'v2026.2.0'), or None
            to auto-detect from the latest hotfix or regular tag.

    Returns:
        A tuple (next_tag, resolved_base_version). For example:
        - ('v2026.2.0-h1-rc0', 'v2026.2.0')
        - ('v2026.2.0-h2-rc0', 'v2026.2.0')
    """
    hotfix_tags = [tag for tag in tags if tag.hotfix is not None]
    resolved_base_version = _resolve_base_version(tags, base_version, True)

    # Find all hotfix tags for this base version
    matching = [
        tag for tag in hotfix_tags
        if (tag.year, tag.minor, tag.patch) == parse_base_version(resolved_base_version)
    ]

    if not matching:
        # First hotfix ever for this base version
        return f"{resolved_base_version}-h1-rc0", resolved_base_version

    max_hotfix_num = max(tag.hotfix for tag in matching)
    next_rc_num = max(
        (tag.rc for tag in matching if tag.hotfix == max_hotfix_num),
        default=-1,
    ) + 1
    return f"{resolved_base_version}-h{max_hotfix_num}-rc{next_rc_num}", resolved_base_version
