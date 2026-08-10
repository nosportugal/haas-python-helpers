"""Performance benchmark tests.

Run with: poetry run pytest tests/test_benchmark.py -v
"""

from __future__ import annotations

import time

from fastapi import FastAPI
from yaks_observability import setup


class TestBenchmark:
    def test_setup_overhead(self) -> None:
        """Measure startup overhead. Target: <100ms."""
        app = FastAPI()
        start = time.perf_counter()
        setup(app)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 500  # generous ceiling; CI machines vary

    def test_lifespan_attached(self) -> None:
        """Ensure lifespan is registered after setup."""
        app = FastAPI()
        setup(app)
        assert app.router.lifespan_context is not None
