"""Derive Confluence page labels from a test case."""

from __future__ import annotations

import re

from sync_confluence.testspec._model import TestCase

_LABEL_INVALID_RE = re.compile(r"[^a-z0-9_-]+")


def page_labels(case: TestCase) -> list[str]:
    """Tags as Confluence-safe labels (lowercase, no spaces, no duplicates)."""
    labels: list[str] = []
    for raw in case.tags:
        label = _LABEL_INVALID_RE.sub("-", raw.casefold()).strip("-")
        if label and label not in labels:
            labels.append(label)
    return labels
