"""Logging filters for health-check noise reduction."""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

# Minimum index for the path argument in uvicorn.access log record.args
_UVICORN_PATH_INDEX = 2


def _match_health_path(raw_path: str, endpoints: tuple[str, ...]) -> bool:
    """Strip query strings and trailing slashes, then match path prefix.

    Args:
        raw_path: The raw request path (may include query string).
        endpoints: Tuple of known health endpoint prefixes.

    Returns:
        True if the path matches a known health endpoint.
    """
    # Strip query strings: /health?foo=bar -> /health
    path = urlsplit(raw_path).path
    stripped = path.rstrip("/") or "/"
    return stripped in endpoints


class HealthCheckFilter(logging.Filter):
    """Suppress access-log records for health probes.

    Designed for uvicorn.access logger where the request path lives in
    ``record.args`` (index 2) when the message format includes it.
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
        """Return ``False`` to drop the record; ``True`` to keep it."""
        # Pattern: uvicorn.access log records have args like:
        #   (client_addr, method, path, http_version, status_code)
        if not hasattr(record, "args") or not record.args:
            return True

        args = record.args
        min_args_needed = _UVICORN_PATH_INDEX + 1
        if len(args) >= min_args_needed and isinstance(args[_UVICORN_PATH_INDEX], str):
            path: str = args[_UVICORN_PATH_INDEX]
            if _match_health_path(path, self.endpoints):
                return False
        return True


class HealthCheckUrlFilter(logging.Filter):
    """Generic filter using a record attribute injected by OTEL ASGI middleware.

    Falls back gracefully if the attribute is absent.
    """

    def __init__(
        self,
        endpoints: tuple[str, ...] | None = None,
        attr_name: str = "http_target",
    ) -> None:
        super().__init__()
        self.endpoints = endpoints or (
            "/health",
            "/readiness",
            "/liveness",
            "/metrics",
            "/healthz",
        )
        self.attr_name = attr_name

    def filter(self, record: logging.LogRecord) -> bool:
        path = getattr(record, self.attr_name, None)
        if isinstance(path, str):
            if _match_health_path(path, self.endpoints):
                return False
        return True
