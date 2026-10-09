"""CLI module."""

from __future__ import annotations

from create_new_rc.cli._args import parse_args
from create_new_rc.cli._main import main

__all__ = ["main", "parse_args"]
