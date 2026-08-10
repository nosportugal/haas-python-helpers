"""Tests for lifespan shutdown behavior."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI

from yaks_observability.lifespan import (
    _managed_lifespan,
    attach_lifespan,
    set_lifespan_state,
)
import yaks_observability.lifespan as _ls


class TestLifespanShutdown:
    def test_set_lifespan_state(self) -> None:
        _ls._GLOBAL_STATE = None
        set_lifespan_state(trace_provider="fake_trace")
        assert _ls._GLOBAL_STATE is not None
        assert _ls._GLOBAL_STATE.trace_provider == "fake_trace"
        _ls._GLOBAL_STATE = None

    def test_managed_lifespan_exists(self) -> None:
        assert _managed_lifespan is not None

    def test_attach_lifespan_when_none(self) -> None:
        app = FastAPI()
        attach_lifespan(app)
        assert app.router.lifespan_context is not None

    def test_attach_lifespan_when_existing(self) -> None:
        @contextlib.asynccontextmanager
        async def existing_lifespan(app_inner: FastAPI) -> AsyncIterator[None]:
            yield

        app = FastAPI(lifespan=existing_lifespan)
        attach_lifespan(app)
        assert app.router.lifespan_context is not _managed_lifespan
