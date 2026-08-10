"""Tests for production resilience defaults."""

from __future__ import annotations

import os

from yaks_observability.resilience import (
    DEFAULT_MAX_EXPORT_BATCH_SIZE,
    DEFAULT_MAX_QUEUE_SIZE,
    DEFAULT_SCHEDULE_DELAY_MS,
    configure_env_defaults,
    get_batch_processor_kwargs,
    get_exporter_kwargs,
)


class TestResilienceDefaults:
    def test_batch_processor_kwargs(self) -> None:
        kwargs = get_batch_processor_kwargs()
        assert kwargs["max_queue_size"] == DEFAULT_MAX_QUEUE_SIZE
        assert kwargs["max_export_batch_size"] == DEFAULT_MAX_EXPORT_BATCH_SIZE
        assert kwargs["schedule_delay_millis"] == DEFAULT_SCHEDULE_DELAY_MS

    def test_exporter_kwargs(self) -> None:
        kwargs = get_exporter_kwargs()
        assert kwargs["timeout"] == 10000

    def test_configure_env_defaults(self) -> None:
        # Ensure defaults are applied when env is empty
        for key in (
            "OTEL_BSP_MAX_QUEUE_SIZE",
            "OTEL_BSP_MAX_EXPORT_BATCH_SIZE",
            "OTEL_BSP_SCHEDULE_DELAY",
        ):
            os.environ.pop(key, None)

        configure_env_defaults()

        assert os.environ["OTEL_BSP_MAX_QUEUE_SIZE"] == str(DEFAULT_MAX_QUEUE_SIZE)
        assert os.environ["OTEL_BSP_MAX_EXPORT_BATCH_SIZE"] == str(
            DEFAULT_MAX_EXPORT_BATCH_SIZE
        )
        assert os.environ["OTEL_BSP_SCHEDULE_DELAY"] == str(DEFAULT_SCHEDULE_DELAY_MS)
