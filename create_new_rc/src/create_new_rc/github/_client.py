"""Low-level GitHub API client via gh CLI."""

from __future__ import annotations

import json
import subprocess


class GitHubAPIError(Exception):
    """Raised when a gh CLI command fails."""

    pass


def gh(*args: str, input_text: str | None = None) -> dict | list | str:
    """Run a gh CLI command and return parsed JSON output.

    Args:
        *args: Arguments to pass to gh (e.g., 'api', '/repos/owner/repo', ...).
        input_text: Optional stdin text to pass to the command.

    Returns:
        Parsed JSON output as dict/list, or plain text string if no JSON.

    Raises:
        GitHubAPIError: If the command returns a non-zero exit code.
    """
    cmd = ["gh", *args]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_text,
    )
    if result.returncode != 0:
        msg = (
            f"Command failed: {' '.join(cmd)}\n"
            f"stderr: {result.stderr.strip()}"
        )
        raise GitHubAPIError(msg)
    if result.stdout.strip():
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            # Some gh commands (e.g. pr create) output plain text; return as-is.
            return result.stdout.strip()
    return {}
