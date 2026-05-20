"""Command-line argument parsing."""

from __future__ import annotations

import argparse


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Explicit argument list. If None, uses sys.argv[1:].

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        prog="create-rc",
        description="Create a release candidate tag and PR.",
    )
    parser.add_argument(
        "--type",
        dest="rc_type",
        choices=["regular", "hotfix"],
        default="regular",
        help="RC type (default: regular)",
    )
    parser.add_argument(
        "--base-version",
        metavar="VERSION",
        help=(
            "Base version, e.g. v2026.2.0 "
            "(optional for regular, recommended for hotfix)"
        ),
    )
    parser.add_argument(
        "--repo",
        metavar="OWNER/REPO",
        help="GitHub repository (default: current repo via gh CLI)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without making any API calls",
    )
    return parser.parse_args(argv)
