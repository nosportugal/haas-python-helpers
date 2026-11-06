"""Environment-variable defaults for command-line options."""

from __future__ import annotations

import os
from typing import Optional


def env_or_default(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read an environment variable, returning *default* if unset or empty."""
    env_value = os.environ.get(name, "")
    return env_value if env_value else default
