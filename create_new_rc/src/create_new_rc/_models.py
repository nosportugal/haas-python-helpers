"""Data models for release candidate tags."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ParsedTag:
    """A parsed release candidate tag.

    Examples:
        v2026.2.0-rc3      → regular RC
        v2026.2.0-h1-rc3   → hotfix RC
    """

    raw: str
    year: int
    minor: int
    patch: int
    hotfix: int | None  # None for regular RCs
    rc: int

    @property
    def base_version(self) -> str:
        """Return the base version string (e.g., 'v2026.2.0')."""
        return f"v{self.year}.{self.minor}.{self.patch}"

    @property
    def base_tuple(self) -> tuple[int, int, int]:
        """Return the base version as a tuple for comparison."""
        return (self.year, self.minor, self.patch)


_RE_REGULAR = re.compile(r"^v(\d+)\.(\d+)\.(\d+)-rc(\d+)$")
_RE_HOTFIX = re.compile(r"^v(\d+)\.(\d+)\.(\d+)-h(\d+)-rc(\d+)$")


def parse_tag(raw: str) -> ParsedTag | None:
    """Parse a git tag into a ParsedTag, or return None if it doesn't match RC patterns.

    Args:
        raw: A git tag string.

    Returns:
        A ParsedTag if the tag matches a known RC pattern, None otherwise.
    """
    # Try hotfix pattern first
    hotfix_match = _RE_HOTFIX.match(raw)
    if hotfix_match:
        return ParsedTag(
            raw=raw,
            year=int(hotfix_match.group(1)),
            minor=int(hotfix_match.group(2)),
            patch=int(hotfix_match.group(3)),
            hotfix=int(hotfix_match.group(4)),
            rc=int(hotfix_match.group(5)),
        )
    # Try regular pattern
    regular_match = _RE_REGULAR.match(raw)
    if regular_match:
        return ParsedTag(
            raw=raw,
            year=int(regular_match.group(1)),
            minor=int(regular_match.group(2)),
            patch=int(regular_match.group(3)),
            hotfix=None,
            rc=int(regular_match.group(4)),
        )
    return None
