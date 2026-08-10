"""Tests for instrumentation error/sampler branches."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


from yaks_observability.config import Environment, ObservabilityConfig
from yaks_observability.instrumentation import (
    _init_logging,
    _init_metrics,
    _init_tracing,
    _resolve_sampler,
    instrument_fastapi,
    shutdown_providers,
)
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_OFF,
    ALWAYS_ON,
    ParentBasedTraceIdRatio,
)


class TestResolveSampler:
    def _make_config(self, sampler: str, arg: str) -> ObservabilityConfig:
        return ObservabilityConfig(
            environment=Environment.DEV,
            service_name="test",
            otlp_endpoint="http://localhost:4318",
            log_level="DEBUG",
            sampler=sampler,
            sampler_arg=arg,
            health_endpoints=("/health",),
            enable_console_json=False,
            enable_otlp_logs=False,
            enable_otlp_traces=False,
            enable_otlp_metrics=False,
            enable_pii_redaction=True,
            testing_mode=True,
        )

    def test_ratio(self) -> None:
        result = _resolve_sampler(self._make_config("parentbased_traceidratio", "0.5"))
        assert isinstance(result, ParentBasedTraceIdRatio)

    def test_always_on(self) -> None:
        result = _resolve_sampler(self._make_config("parentbased_always_on", "1.0"))
        assert result is ALWAYS_ON

    def test_always_off(self) -> None:
        result = _resolve_sampler(self._make_config("parentbased_always_off", "0.0"))
        assert result is ALWAYS_OFF

    def test_unknown_fallback(self) -> None:
        result = _resolve_sampler(self._make_config("foo_bar", "0.25"))
        assert isinstance(result, ParentBasedTraceIdRatio)

    def test_disabled_traces(self) -> None:
        config = self._make_config("parentbased_always_on", "1.0")
        result = _init_tracing(config, MagicMock())
        assert result is None

    def test_tracing_error(self) -> None:
        config = ObservabilityConfig(
            environment=Environment.DEV,
            service_name="test",
            otlp_endpoint="http://localhost:4318",
            log_level="DEBUG",
            sampler="parentbased_always_on",
            sampler_arg="1.0",
            health_endpoints=("/health",),
            enable_console_json=False,
            enable_otlp_logs=False,
            enable_otlp_traces=True,
            enable_otlp_metrics=False,
            enable_pii_redaction=True,
            testing_mode=False,
        )
        with patch(
            "yaks_observability.instrumentation._build_tracer_provider",
            side_effect=RuntimeError("boom"),
        ):
            result = _init_tracing(config, MagicMock())
        assert result is None

    def test_logging_error(self) -> None:
        config = ObservabilityConfig(
            environment=Environment.DEV,
            service_name="test",
            otlp_endpoint="http://localhost:4318",
            log_level="DEBUG",
            sampler="parentbased_always_on",
            sampler_arg="1.0",
            health_endpoints=("/health",),
            enable_console_json=False,
            enable_otlp_logs=True,
            enable_otlp_traces=False,
            enable_otlp_metrics=False,
            enable_pii_redaction=True,
            testing_mode=False,
        )
        with patch(
            "yaks_observability.instrumentation._create_log_provider",
            side_effect=RuntimeError("boom"),
        ):
            result = _init_logging(config, MagicMock())
        assert result is None

    def test_metrics_error(self) -> None:
        config = ObservabilityConfig(
            environment=Environment.DEV,
            service_name="test",
            otlp_endpoint="http://localhost:4318",
            log_level="DEBUG",
            sampler="parentbased_always_on",
            sampler_arg="1.0",
            health_endpoints=("/health",),
            enable_console_json=False,
            enable_otlp_logs=False,
            enable_otlp_traces=False,
            enable_otlp_metrics=True,
            enable_pii_redaction=True,
            testing_mode=False,
        )
        with patch(
            "yaks_observability.instrumentation.otlp_metrics_http.OTLPMetricExporter",
            side_effect=RuntimeError("boom"),
        ):
            result = _init_metrics(config, MagicMock())
        assert result is None

    def test_fastapi_error(self) -> None:
        app = MagicMock()
        config = ObservabilityConfig(
            environment=Environment.DEV,
            service_name="test",
            otlp_endpoint="http://localhost:4318",
            log_level="DEBUG",
            sampler="parentbased_always_on",
            sampler_arg="1.0",
            health_endpoints=("/health",),
            enable_console_json=False,
            enable_otlp_logs=False,
            enable_otlp_traces=False,
            enable_otlp_metrics=False,
            enable_pii_redaction=True,
            testing_mode=False,
        )
        # FastAPIInstrumentor is imported locally inside instrument_fastapi
        # We patch inside the function via builtins.__import__ or just call
        # instrument_fastapi directly with a side_effect on the actual import.
        # Simpler: use patch on the module's local import context via patch.dict
        import sys
        fake = MagicMock()
        fake.FastAPIInstrumentor.instrument_app.side_effect = RuntimeError("boom")
        with patch.dict(sys.modules, {"opentelemetry.instrumentation.fastapi": fake}):
            result = instrument_fastapi(app, config)
        assert result is None


class TestShutdownProviders:
    def test_trace_provider_force_flush_error(self) -> None:
        trace_mock = MagicMock()
        trace_mock.force_flush.side_effect = RuntimeError("flush err")
        shutdown_providers(trace_mock, None, None)
        trace_mock.force_flush.assert_called_once()

    def test_log_provider_force_flush_error(self) -> None:
        log_mock = MagicMock()
        log_mock.force_flush.side_effect = RuntimeError("flush err")
        shutdown_providers(None, log_mock, None)
        log_mock.force_flush.assert_called_once()

    def test_metric_provider_force_flush_error(self) -> None:
        metric_mock = MagicMock()
        metric_mock.force_flush.side_effect = RuntimeError("flush err")
        shutdown_providers(None, None, metric_mock)
        metric_mock.force_flush.assert_called_once()

    def test_all_none(self) -> None:
        shutdown_providers(None, None, None)

    def test_trace_shutdown_error(self) -> None:
        trace_mock = MagicMock()
        trace_mock.shutdown.side_effect = RuntimeError("shutdown err")
        shutdown_providers(trace_mock, None, None)
