"""Tests for graceful degradation utilities."""

from __future__ import annotations


from yaks_observability.graceful_degradation import (
    instrument_httpx,
    instrument_requests,
    instrument_sqlalchemy,
    safe_import,
    suppress_otel_errors,
)


class TestSafeImport:
    def test_import_existing(self) -> None:
        mod = safe_import("logging")
        assert mod is not None

    def test_import_missing(self) -> None:
        mod = safe_import("totally_fake_module_xyz")
        assert mod is None


class TestSuppressOtelErrors:
    def test_noop_on_success(self) -> None:
        with suppress_otel_errors():
            result = 42
        assert result == 42

    def test_suppresses_exception(self) -> None:
        with suppress_otel_errors():
            raise ValueError("expected")
        # Should not propagate


class TestInstrumentorsNoopWithoutDeps:
    def test_sqlalchemy_no_engine(self) -> None:
        # Passing None engine should not raise
        instrument_sqlalchemy(None)

    def test_httpx_no_dep(self) -> None:
        # If otel instrumentation is missing, should not raise
        instrument_httpx()

    def test_requests_no_dep(self) -> None:
        instrument_requests()
