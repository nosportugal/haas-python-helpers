"""Tests for logging filters."""

from __future__ import annotations

import logging

from yaks_observability.filters import HealthCheckFilter


class TestHealthCheckFilter:
    def test_keeps_regular_request(self) -> None:
        f = HealthCheckFilter()
        record = logging.LogRecord(
            name="uvicorn.access",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg='%s - "%s %s HTTP/%s" %d',
            args=("127.0.0.1", "GET", "/api/v1/data", "1.1", 200),
            exc_info=None,
        )
        assert f.filter(record) is True

    def test_drops_health_request(self) -> None:
        f = HealthCheckFilter()
        record = logging.LogRecord(
            name="uvicorn.access",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg='%s - "%s %s HTTP/%s" %d',
            args=("127.0.0.1", "GET", "/health", "1.1", 200),
            exc_info=None,
        )
        assert f.filter(record) is False

    def test_drops_readiness(self) -> None:
        f = HealthCheckFilter()
        record = logging.LogRecord(
            name="uvicorn.access",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg='%s - "%s %s HTTP/%s" %d',
            args=("127.0.0.1", "GET", "/readiness", "1.1", 200),
            exc_info=None,
        )
        assert f.filter(record) is False

    def test_keeps_failed_health_request(self) -> None:
        f = HealthCheckFilter()
        record = logging.LogRecord(
            name="uvicorn.access",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg='%s - "%s %s HTTP/%s" %d',
            args=("127.0.0.1", "GET", "/health", "1.1", 500),
            exc_info=None,
        )
        assert f.filter(record) is True

    def test_keeps_bad_gateway(self) -> None:
        f = HealthCheckFilter()
        record = logging.LogRecord(
            name="uvicorn.access",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg='%s - "%s %s HTTP/%s" %d',
            args=("127.0.0.1", "GET", "/readiness", "1.1", 502),
            exc_info=None,
        )
        assert f.filter(record) is True

    def test_drops_when_no_status(self) -> None:
        f = HealthCheckFilter()
        record = logging.LogRecord(
            name="uvicorn.access",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg='%s - "%s %s HTTP/%s"',
            args=("127.0.0.1", "GET", "/health", "1.1"),
            exc_info=None,
        )
        assert f.filter(record) is False

    def test_trailing_slash_match(self) -> None:
        f = HealthCheckFilter()
        record = logging.LogRecord(
            name="uvicorn.access",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg='%s - "%s %s HTTP/%s" %d',
            args=("127.0.0.1", "GET", "/health/", "1.1", 200),
            exc_info=None,
        )
        assert f.filter(record) is False

    def test_keeps_non_uvicorn_logger(self) -> None:
        f = HealthCheckFilter()
        record = logging.LogRecord(
            name="other.logger",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        assert f.filter(record) is True

    def test_custom_endpoints(self) -> None:
        f = HealthCheckFilter(endpoints=("/ping",))
        record = logging.LogRecord(
            name="uvicorn.access",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg='%s - "%s %s HTTP/%s" %d',
            args=("127.0.0.1", "GET", "/ping", "1.1", 200),
            exc_info=None,
        )
        assert f.filter(record) is False
