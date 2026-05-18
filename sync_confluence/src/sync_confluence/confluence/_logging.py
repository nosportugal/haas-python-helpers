"""Logging helpers: a filter and context manager to silence noisy library logs."""

from __future__ import annotations

import contextlib
import logging

log = logging.getLogger(__name__)


class _ConfluenceNotFoundFilter(logging.Filter):
    """Filter out 'Can't find' messages from the atlassian library."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: WPS125
        return "Can't find" not in record.getMessage()


@contextlib.contextmanager
def _suppress_atlassian_not_found():
    """Silence the atlassian-python-api ERROR logged when a title lookup
    returns no results.  'Not found' is an expected outcome during upsert;
    real errors surface through exceptions, not through that log message.
    """
    atlassian_logger = logging.getLogger("atlassian.confluence")
    log_filter = _ConfluenceNotFoundFilter()
    atlassian_logger.addFilter(log_filter)
    try:
        yield
    finally:
        atlassian_logger.removeFilter(log_filter)
