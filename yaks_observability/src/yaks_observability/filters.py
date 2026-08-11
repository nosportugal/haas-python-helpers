"""Logging filters for health-check noise reduction."""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

# Minimum index for the path argument in uvicorn.access log record.args
_UVICORN_PATH_INDEX = 2
# Status code is the last element in uvicorn.access log record.args
_UVICORN_STATUS_INDEX = 4
# HTTP status code threshold for treating a response as an error
_HTTP_ERROR_THRESHOLD = 400


def _match_health_path(raw_path: str, endpoints: tuple[str, ...]) -> bool:
    """Strip query strings and trailing slashes, then match exact path.

    Args:
        raw_path: The raw request path (may include query string).
        endpoints: Tuple of known health endpoint paths.

    Returns:
        True if the path matches a known health endpoint.
    """
    # Strip query strings: /health?foo=bar -> /health
    path = urlsplit(raw_path).path
    stripped = path.rstrip("/") or "/"
    return stripped in endpoints


class HealthCheckFilter(logging.Filter):
    """Suppress access-log records for known health endpoints.

    Matches the request path exactly (after stripping query-strings and
    trailing slashes).  Designed for uvicorn.access logger where the
    request path lives in ``record.args`` (index 2).
    """

    def __init__(self, endpoints: tuple[str, ...] | None = None) -> None:
        super().__init__()
        self.endpoints = endpoints or (
            "/health",
            "/readiness",
            "/liveness",
            "/metrics",
            "/healthz",
        )

    def filter(self, record: logging.LogRecord) -> bool:
        """Return ``False`` to drop the record; ``True`` to keep it.

        Successful health checks (2xx/3xx) are suppressed.
        Failed health checks (4xx/5xx) are kept for diagnostics.
        """
        if not hasattr(record, "args") or not record.args:
            return True

        args = record.args
        path = None
        status = None

        if len(args) >= _UVICORN_PATH_INDEX + 1 and isinstance(
            args[_UVICORN_PATH_INDEX], str
        ):
            path = args[_UVICORN_PATH_INDEX]
        if len(args) >= _UVICORN_STATUS_INDEX + 1 and isinstance(
            args[_UVICORN_STATUS_INDEX], int
        ):
            status = args[_UVICORN_STATUS_INDEX]

        if path is None:
            return True

        if not _match_health_path(path, self.endpoints):
            return True

        # Keep failed health checks for diagnostics
        if status is not None and status >= _HTTP_ERROR_THRESHOLD:
            return True

        return False
