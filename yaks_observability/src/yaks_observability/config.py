"""Environment-aware configuration for observability."""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass, field
from enum import Enum


class Environment(str, Enum):
    """Supported runtime environments."""

    DEV = "dev"
    QA = "qa"
    PROD = "prod"
    TESTING = "testing"


class LogLevel(str, Enum):
    """Standard log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# Environment → log level mapping (default)
DEFAULT_LOG_LEVELS: dict[Environment, str] = {
    Environment.DEV: LogLevel.DEBUG.value,
    Environment.QA: LogLevel.INFO.value,
    Environment.PROD: LogLevel.WARN.value,
    Environment.TESTING: LogLevel.DEBUG.value,
}

# Environment → default sampler mapping
DEFAULT_SAMPLERS: dict[Environment, tuple[str, str]] = {
    Environment.DEV: ("parentbased_always_on", "1.0"),
    Environment.QA: ("parentbased_traceidratio", "0.5"),
    Environment.PROD: ("parentbased_traceidratio", "0.1"),
    Environment.TESTING: ("parentbased_always_off", "0.0"),
}

# Endpoints considered health checks
DEFAULT_HEALTH_ENDPOINTS: tuple[str, ...] = (
    "/health",
    "/readiness",
    "/liveness",
    "/metrics",
    "/healthz",  # k8s common
)


@dataclass(frozen=True, slots=True)
class ObservabilityConfig:
    """Immutable configuration resolved from environment variables."""

    environment: Environment
    service_name: str
    log_level: str
    sampler: str
    sampler_arg: str
    health_endpoints: tuple[str, ...]
    enable_console_json: bool
    enable_otlp_logs: bool
    enable_otlp_traces: bool
    enable_otlp_metrics: bool
    enable_pii_redaction: bool
    testing_mode: bool
    otlp_endpoint: str = ""
    otlp_traces_endpoint: str = ""
    otlp_logs_endpoint: str = ""
    otlp_metrics_endpoint: str = ""
    service_namespace: str = ""
    service_version: str = ""
    service_instance_id: str = ""
    pii_safe_keys: tuple[str, ...] = ()
    pii_body_patterns: tuple[str, ...] = ()
    extra_resource_attributes: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> ObservabilityConfig:  # noqa: PLR0914
        """Build configuration from environment variables with sensible defaults."""
        env_raw = os.getenv("ENVIRONMENT_TYPE", "dev").lower()
        try:
            environment = Environment(env_raw)
        except ValueError:
            environment = Environment.DEV

        testing_mode = environment == Environment.TESTING
        service_name = os.getenv("OTEL_SERVICE_NAME", "")
        if not service_name and not testing_mode:
            service_name = "unknown-service"
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
        otlp_traces_endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "")
        otlp_logs_endpoint = os.getenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "")
        otlp_metrics_endpoint = os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "")
        log_level = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVELS[environment])
        default_sampler, default_arg = DEFAULT_SAMPLERS[environment]
        sampler = os.getenv("OTEL_TRACES_SAMPLER", default_sampler)
        sampler_arg = os.getenv("OTEL_TRACES_SAMPLER_ARG", default_arg)
        health_endpoints = _parse_health_endpoints()
        toggle = _parse_feature_toggles(testing_mode)
        raw_attrs = os.getenv("OTEL_RESOURCE_ATTRIBUTES", "")
        extra_resource_attributes = _parse_resource_attrs(raw_attrs)

        service_namespace = os.getenv("OTEL_SERVICE_NAMESPACE", "")
        service_version = os.getenv("OTEL_SERVICE_VERSION", "")
        service_instance_id = os.getenv("OTEL_SERVICE_INSTANCE_ID", "") or (
            socket.gethostname()
        )
        pii_safe_keys = _parse_comma_list(os.getenv("OTEL_PII_SAFE_KEYS", ""))
        pii_body_patterns = _parse_comma_list(os.getenv("OTEL_PII_BODY_PATTERNS", ""))

        return cls(
            environment=environment,
            service_name=service_name,
            service_namespace=service_namespace,
            service_version=service_version,
            service_instance_id=service_instance_id,
            otlp_endpoint=otlp_endpoint,
            otlp_traces_endpoint=otlp_traces_endpoint,
            otlp_logs_endpoint=otlp_logs_endpoint,
            otlp_metrics_endpoint=otlp_metrics_endpoint,
            log_level=log_level,
            sampler=sampler,
            sampler_arg=sampler_arg,
            health_endpoints=health_endpoints,
            enable_console_json=toggle["enable_console_json"],
            enable_otlp_logs=toggle["enable_otlp_logs"],
            enable_otlp_traces=toggle["enable_otlp_traces"],
            enable_otlp_metrics=toggle["enable_otlp_metrics"],
            enable_pii_redaction=toggle["enable_pii_redaction"],
            pii_safe_keys=pii_safe_keys,
            pii_body_patterns=pii_body_patterns,
            testing_mode=testing_mode,
            extra_resource_attributes=extra_resource_attributes,
        )


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name, "").lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_health_endpoints() -> tuple[str, ...]:
    health_raw = os.getenv("OTEL_HEALTH_ENDPOINTS", "")
    parsed = tuple(ep.strip() for ep in health_raw.split(",") if ep.strip())
    return parsed or DEFAULT_HEALTH_ENDPOINTS


def _parse_feature_toggles(testing_mode: bool) -> dict[str, bool]:
    return {
        "enable_console_json": _bool_env("OTEL_ENABLE_CONSOLE_JSON", False),
        "enable_otlp_logs": _bool_env(
            "OTEL_EXPORTER_OTLP_LOGS_ENABLED", not testing_mode
        ),
        "enable_otlp_traces": _bool_env(
            "OTEL_EXPORTER_OTLP_TRACES_ENABLED", not testing_mode
        ),
        "enable_otlp_metrics": _bool_env(
            "OTEL_EXPORTER_OTLP_METRICS_ENABLED", not testing_mode
        ),
        "enable_pii_redaction": _bool_env("OTEL_ENABLE_PII_REDACTION", True),
    }


def _parse_comma_list(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _parse_resource_attrs(raw: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for raw_item in raw.split(","):
        item = raw_item.strip()
        if "=" in item:
            key, value = item.split("=", 1)
            attrs[key.strip()] = value.strip()
    return attrs
