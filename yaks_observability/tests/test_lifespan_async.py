"""Async tests for lifespan shutdown paths."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI

from yaks_observability.lifespan import (
    _managed_lifespan,
    set_lifespan_state,
)
import yaks_observability.lifespan as _ls


@pytest.mark.anyio
class TestManagedLifespanAsync:
    async def test_yields_and_runs_shutdown(self) -> None:
        trace_mock = MagicMock()
        log_mock = MagicMock()
        metric_mock = MagicMock()
        _ls._GLOBAL_STATE = None
        set_lifespan_state(
            trace_provider=trace_mock,
            log_provider=log_mock,
            metric_provider=metric_mock,
        )
        app = FastAPI()
        async with _managed_lifespan(app):
            pass
        trace_mock.force_flush.assert_called_once()
        trace_mock.shutdown.assert_called_once()
        log_mock.force_flush.assert_called_once()
        log_mock.shutdown.assert_called_once()
        metric_mock.force_flush.assert_called_once()
        metric_mock.shutdown.assert_called_once()

    async def test_noop_when_no_state(self) -> None:
        _ls._GLOBAL_STATE = None
        app = FastAPI()
        async with _managed_lifespan(app):
            pass

    async def test_shutdown_suppressed_error(self) -> None:
        trace_mock = MagicMock()
        trace_mock.force_flush.side_effect = RuntimeError("boom")
        _ls._GLOBAL_STATE = None
        set_lifespan_state(trace_provider=trace_mock)
        app = FastAPI()
        async with _managed_lifespan(app):
            pass
        trace_mock.force_flush.assert_called_once()
