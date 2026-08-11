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
        _ls._APP_STATE.clear()
        set_lifespan_state(trace_provider="fake_trace")
        assert len(_ls._APP_STATE) == 1
        state = next(iter(_ls._APP_STATE.values()))
        assert state.trace_provider == "fake_trace"
        _ls._APP_STATE.clear()

    def test_managed_lifespan_exists(self) -> None:
        assert _managed_lifespan is not None

    def test_attach_lifespan_when_none(self) -> None:
        app = FastAPI()
        attach_lifespan(app)
        assert app.router.lifespan_context is not None
        assert getattr(app.router, "_yaks_lifespan_wrapped", False)

    def test_attach_lifespan_when_existing(self) -> None:
        @contextlib.asynccontextmanager
        async def existing_lifespan(app_inner: FastAPI) -> AsyncIterator[None]:
            yield

        app = FastAPI(lifespan=existing_lifespan)
        attach_lifespan(app)
        assert app.router.lifespan_context is not _managed_lifespan

    def test_attach_lifespan_idempotent(self) -> None:
        app = FastAPI()
        attach_lifespan(app)
        first = app.router.lifespan_context
        attach_lifespan(app)
        assert app.router.lifespan_context is first
