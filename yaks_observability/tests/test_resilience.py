"""Tests for production resilience defaults."""

from __future__ import annotations

from yaks_observability.resilience import (
    DEFAULT_MAX_EXPORT_BATCH_SIZE,
    DEFAULT_MAX_QUEUE_SIZE,
    DEFAULT_SCHEDULE_DELAY_MS,
    get_batch_processor_kwargs,
    get_exporter_kwargs,
)


class TestResilienceDefaults:
    def test_batch_processor_kwargs(self) -> None:
        kwargs = get_batch_processor_kwargs()
        assert kwargs["max_queue_size"] == DEFAULT_MAX_QUEUE_SIZE
        assert kwargs["max_export_batch_size"] == DEFAULT_MAX_EXPORT_BATCH_SIZE
        assert kwargs["schedule_delay_millis"] == DEFAULT_SCHEDULE_DELAY_MS

    def test_batch_processor_kwargs_override(self) -> None:
        kwargs = get_batch_processor_kwargs(
            max_queue_size=1024,
            max_export_batch_size=256,
            schedule_delay_millis=1000,
        )
        assert kwargs["max_queue_size"] == 1024
        assert kwargs["max_export_batch_size"] == 256
        assert kwargs["schedule_delay_millis"] == 1000

    def test_exporter_kwargs(self) -> None:
        kwargs = get_exporter_kwargs()
        assert kwargs["timeout"] == 10000

    def test_exporter_kwargs_override(self) -> None:
        kwargs = get_exporter_kwargs(timeout=5000)
        assert kwargs["timeout"] == 5000
