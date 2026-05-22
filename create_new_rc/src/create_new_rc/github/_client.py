"""Low-level GitHub API client via gh CLI."""

from __future__ import annotations

import json
import subprocess


class GitHubAPIError(Exception):
    """Raised when a gh CLI command fails."""


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
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_text,
    )
    if completed.returncode != 0:
        cmd_str = " ".join(cmd)
        stderr_str = completed.stderr.strip()
        raise GitHubAPIError(f"Command failed: {cmd_str}\nstderr: {stderr_str}")
    if completed.stdout.strip():
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError:
            # Some gh commands (e.g. pr create) output plain text; return as-is.
            return completed.stdout.strip()
    return {}
