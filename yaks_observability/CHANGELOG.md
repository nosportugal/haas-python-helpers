# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- PII redaction on console/stdout output (`_PIIRedactionFilter` on StreamHandler).
- `_OtelInternalFilter` on the OTLP `LoggingHandler` to break the feedback loop when
  the collector is down.
- `py.typed` marker for downstream type-checking support.
- `CHANGELOG.md` and `SECURITY.md`.
- Regression tests covering collector-down bounded shutdown and console PII leakage.

### Fixed

- **P0:** OTLP log feedback loop — exporter failure logs no longer re-enter the
  export pipeline, preventing indefinite hangs when the collector is unreachable.
- **P0:** Console PII redaction gap — stdout logs now scrub PII when
  `enable_pii_redaction=True`.
- **P1:** Moved CI workflow from `yaks_observability/.github/workflows/` to the
  repo root so GitHub Actions actually executes it.
- **P1:** Removed stale `dist/` wheel and `htmlcov/` coverage files from the repo.
- **P2:** Replaced stdlib `logging` module monkeypatch with a module-level flag.
- **P2:** Per-app lifespan/provider state prevents duplicate handler attachments
  on repeated `setup()` calls.

### Changed

- `configure_logging` now sets `opentelemetry` logger to `propagate=False` in all
  environments (previously only set level to WARNING in testing mode).

## [1.0.0] — 2025-08-10

### Added

- Initial GA release with full OpenTelemetry support (traces, logs, metrics).
- Environment-aware structured logging (JSON/text).
- Health-check log filtering for uvicorn.access.
- PII redaction before OTLP export via filtering exporter wrappers.
- Graceful degradation for missing dependencies and unreachable collectors.
- FastAPI auto-instrumentation with trace context propagation.
- Downstream instrumentation for SQLAlchemy, httpx, and requests.

[Unreleased]: https://github.com/nosportugal/haas-python-helpers/compare/yaks-observability-1.0.0...HEAD
[1.0.0]: https://github.com/nosportugal/haas-python-helpers/releases/tag/yaks-observability-1.0.0
