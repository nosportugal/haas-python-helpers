"""Tests for logging filters."""

from __future__ import annotations

import logging

from yaks_observability.filters import HealthCheckFilter, HealthCheckUrlFilter


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

    def test_keeps_when_no_args(self) -> None:
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


class TestHealthCheckUrlFilter:
    def test_attr_match(self) -> None:
        f = HealthCheckUrlFilter()
        record = logging.LogRecord(
            name="app",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="request",
            args=(),
            exc_info=None,
        )
        record.http_target = "/health"
        assert f.filter(record) is False

    def test_attr_no_match(self) -> None:
        f = HealthCheckUrlFilter()
        record = logging.LogRecord(
            name="app",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="request",
            args=(),
            exc_info=None,
        )
        record.http_target = "/api/data"
        assert f.filter(record) is True

    def test_missing_attr(self) -> None:
        f = HealthCheckUrlFilter()
        record = logging.LogRecord(
            name="app",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="request",
            args=(),
            exc_info=None,
        )
        assert f.filter(record) is True

    def test_query_string_stripped(self) -> None:
        f = HealthCheckUrlFilter()
        record = logging.LogRecord(
            name="app", level=logging.INFO, pathname="", lineno=1,
            msg="request", args=(), exc_info=None,
        )
        record.http_target = "/health?foo=bar"
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
