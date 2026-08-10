"""Tests for graceful degradation utilities."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
    def test_sqlalchemy_no_dep(self) -> None:
        instrument_sqlalchemy(None)

    def test_httpx_no_dep(self) -> None:
        instrument_httpx()

    def test_requests_no_dep(self) -> None:
        instrument_requests()


class TestInstrumentorsWithMockDeps:
    def _mock_module(self, cls_name: str, method_side_effect=None):
        mock_mod = MagicMock()
        mock_inst = MagicMock()
        if method_side_effect:
            mock_inst.instrument.side_effect = method_side_effect
        getattr(mock_mod, cls_name).return_value = mock_inst
        return mock_mod, mock_inst

    def test_sqlalchemy_success(self) -> None:
        mock_mod, mock_inst = self._mock_module("SQLAlchemyInstrumentor")
        with patch(
            "yaks_observability.graceful_degradation.safe_import",
            return_value=mock_mod,
        ):
            instrument_sqlalchemy("fake_engine")
        mock_inst.instrument.assert_called_once_with(engine="fake_engine")

    def test_sqlalchemy_exception(self) -> None:
        mock_mod, mock_inst = self._mock_module(
            "SQLAlchemyInstrumentor", RuntimeError("boom")
        )
        with patch(
            "yaks_observability.graceful_degradation.safe_import",
            return_value=mock_mod,
        ):
            instrument_sqlalchemy("fake_engine")
        mock_inst.instrument.assert_called_once()

    def test_httpx_success(self) -> None:
        mock_mod, mock_inst = self._mock_module("HTTPXClientInstrumentor")
        with patch(
            "yaks_observability.graceful_degradation.safe_import",
            return_value=mock_mod,
        ):
            instrument_httpx()
        mock_inst.instrument.assert_called_once()

    def test_httpx_exception(self) -> None:
        mock_mod, mock_inst = self._mock_module(
            "HTTPXClientInstrumentor", RuntimeError("boom")
        )
        with patch(
            "yaks_observability.graceful_degradation.safe_import",
            return_value=mock_mod,
        ):
            instrument_httpx()
        mock_inst.instrument.assert_called_once()

    def test_requests_success(self) -> None:
        mock_mod, mock_inst = self._mock_module("RequestsInstrumentor")
        with patch(
            "yaks_observability.graceful_degradation.safe_import",
            return_value=mock_mod,
        ):
            instrument_requests()
        mock_inst.instrument.assert_called_once()

    def test_requests_exception(self) -> None:
        mock_mod, mock_inst = self._mock_module(
            "RequestsInstrumentor", RuntimeError("boom")
        )
        with patch(
            "yaks_observability.graceful_degradation.safe_import",
            return_value=mock_mod,
        ):
            instrument_requests()
        mock_inst.instrument.assert_called_once()
