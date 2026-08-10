# yaks-observability — Remediation Plan (post-peaky review)

Status: **not GA-ready**. The PII redaction pillar is non-functional for both signals, the committed test suite is red and non-terminating, and programmatic config is partly ignored.

This plan closes every blocker found in the Staff Logging Engineer re-review. Work is ordered by ship-priority. Each item lists **Description**, **What is needed**, **Definition of Done (DoD)**, and **Deliverable**.

---

## Priority 0 — Ship-blockers (must fix before GA)

### F1. PII span redaction (`fix-pii-span-mappingproxy`)

**Description.**
`PIIRedactingSpanProcessor.on_end` guards on `isinstance(span.attributes, dict)`. On a real SDK span `span.attributes` is a read-only `mappingproxy`, so the guard is always `False` and redaction never runs. There is no attribute setter either, so in-place mutation is impossible. Result: spans are exported with secrets intact (verified: `password: hunter2` present in exported span).

**What is needed.**
- Replace the mutating `SpanProcessor` approach with a **filtering `SpanExporter` wrapper**.
- Wrapper implements `export(spans)` by rebuilding each span's attributes into a plain `dict`, running `scrub_dict`, and constructing a redacted view before delegating to the wrapped OTLP/console exporter.
- Redact standard secret-bearing span attributes and any key matching the PII patterns (`password`, `authorization`, `token`, `secret`, `api_key`, `set-cookie`, email/CPF/card values, etc.).
- Wire the wrapper around the real exporter inside `_build_tracer_provider`; drop `PIIRedactingSpanProcessor` from the processor chain.

**Definition of Done.**
- A test using an in-memory exporter asserts the **exported** span carries `[REDACTED]` for every seeded secret and preserves all non-PII attributes.
- No `mappingproxy`/`isinstance(..., dict)` guard remains in the span path.
- `password`, `authorization`, `token` never leave the process in span attributes.

**Deliverable.** `RedactingSpanExporter` in `pii_redaction.py`, wired in `instrumentation.py`, covered by a real-exporter test.

---

### F2. PII log redaction (`fix-pii-log-boundedattrs`)

**Description.**
`PIIRedactingLogProcessor.on_emit` guards on `isinstance(log_record.attributes, dict)`. The real object is `BoundedAttributes` (a `MutableMapping`, not a `dict` subclass), so the guard is always `False` and redaction is skipped; `BoundedAttributes` also rejects item assignment. Result: logs are exported with secrets intact (verified: `password: hunter2` present in exported log).

**What is needed.**
- Prefer a **filtering `LogRecordExporter` wrapper** symmetrical to F1: rebuild `dict(record.attributes)`, run `scrub_dict`, and emit a redacted record.
- Also scrub the log **body** when it is a string/mapping (secrets frequently land in the message, not just attributes).
- Remove the dead `isinstance(..., dict)` processor path.

**Definition of Done.**
- A real in-memory log-exporter test asserts exported records have `[REDACTED]` for seeded secrets in both attributes and body.
- No reliance on `dict` identity of `BoundedAttributes`.

**Deliverable.** `RedactingLogExporter` (or equivalent) in `pii_redaction.py`, wired in `_create_log_provider`, covered by a real-exporter test.

---

### F3. Red / non-terminating test suite (`fix-red-test-suite`)

**Description.**
`test_behavioral.py::TestPIISpanProcessor::test_span_processor_receives_redaction` fails against a real `TracerProvider`. The MagicMock-based `test_pii_processor.py` passes falsely (mock `.attributes` is a real dict). The full suite also **hangs**: exporter/setup tests in non-testing mode spawn real OTLP exporters that retry `localhost:4318` with exponential backoff, so `poetry run task test` never completes.

**What is needed.**
- Replace all MagicMock redaction assertions with **real in-memory exporter** assertions (`InMemorySpanExporter`, `InMemoryLogExporter`, `InMemoryMetricReader`).
- Add an **offline guard**: tests must never hit the network. Force in-memory exporters via test fixtures / testing mode; assert no socket to `:4318`.
- Make the suite deterministic and fast (target < a few seconds, no retry backoff).
- Suite must be **green** and terminate; `--cov-fail-under=90` (repo standard) or the package's 95% target must pass without hanging.

**Definition of Done.**
- `poetry run task test` (or `pytest tests/`) completes with **0 failures** and no hang, offline.
- No test depends on a live collector; no MagicMock stands in for a real SDK attribute container.

**Deliverable.** Reworked `test_behavioral.py`, deleted/replaced `test_pii_processor.py`, in-memory fixtures in `conftest.py`, green CI run.

---

## Priority 1 — High

### F4. `config.otlp_endpoint` silently ignored (`fix-config-endpoint-ignored`)

**Description.**
Exporters are built with no `endpoint=`, so only `OTEL_EXPORTER_OTLP_*` env vars are honored. The documented programmatic field `config.otlp_endpoint` (set in `test_setup.py:51`) has zero effect and survives only in a debug log line — misleading.

**What is needed.**
- Decide and implement one behavior:
  - **(a)** Wire `config.otlp_endpoint` into every exporter (`endpoint=`), with env vars taking precedence per OTEL spec; **or**
  - **(b)** Remove the field and document env-only configuration.
- Recommended: **(a)** — honor programmatic config, document precedence (explicit arg > env > default).

**Definition of Done.**
- Setting `config.otlp_endpoint` provably changes the exporter target (asserted via exporter introspection or a captured endpoint).
- Precedence documented in README.

**Deliverable.** Endpoint plumbing in `_create_trace_exporter`/`_create_log_provider`/`_build_metrics_provider`, a test asserting effect, README note.

---

### F5. Non-idempotent `setup()` / duplicate OTLP handler (`fix-otlp-handler-idempotency`)

**Description.**
`_create_log_provider` calls `logging.getLogger().addHandler(handler)` unconditionally (`instrumentation.py:176`) with no `_yaks_handler` marker guard → calling `setup()` twice double-exports every log. `set_logger_provider` / `set_meter_provider` / `LoggingInstrumentor.instrument()` are single-shot and warn on re-call.

**What is needed.**
- Tag the OTLP handler with a `_yaks_handler` marker and skip if already present (mirror the console-handler idempotency guard already in `logging_config.py`).
- Guard provider/instrumentor registration so repeated `setup()` is a safe no-op (check global provider identity or a module-level `_configured` flag).

**Definition of Done.**
- Calling `setup(app)` twice results in exactly one OTLP handler, one logger/meter provider, one instrumentation — asserted by test.
- No "Overriding ... not allowed" warnings on second call.

**Deliverable.** Idempotency guards in `instrumentation.py`/`setup.py`, a double-setup test.

---

## Priority 2 — Medium

### F6. Metrics provider has no instruments (`fix-metrics-no-instruments`)

**Description.**
`_build_metrics_provider` wires a `MeterProvider` + reader but registers zero instruments. The package emits no metrics of its own; it relies entirely on `FastAPIInstrumentor`. Acceptable only if intentional and documented — currently neither.

**What is needed.**
- Either register baseline instruments (request counter, latency histogram, error counter) via a shared meter, **or** explicitly document that HTTP metrics come from `FastAPIInstrumentor` and the package intentionally adds none.
- Recommended: document reliance on `FastAPIInstrumentor` and expose a `get_meter()` helper for app-level custom instruments.

**Definition of Done.**
- Behavior documented in README; if instruments added, a test asserts they emit via `InMemoryMetricReader`.

**Deliverable.** README metrics section + optional `get_meter()` helper/test.

### F7. Dead health filter on OTLP handler

**Description.**
`HealthCheckUrlFilter` reads `record.http_target`, which uvicorn access records never set (path is in `record.args[2]`). The filter is inert. Health filtering still works via the `uvicorn.access` `HealthCheckFilter`, making this one redundant.

**What is needed.**
- Remove `HealthCheckUrlFilter`, or fix it to read the correct field and cover it with a test using a realistic uvicorn access record.

**Definition of Done.**
- No dead filter remains; health-path suppression is covered by a test asserting the record is dropped.

**Deliverable.** Cleaned `filters.py` + test.

### F8. Prod log level starves the OTLP pipeline

**Description.**
Root level = `config.log_level` (WARN in prod) gates records before the DEBUG OTLP handler, so INFO logs never reach the collector in prod — likely undesirable for a logs pipeline.

**What is needed.**
- Decouple pipeline verbosity from console verbosity: set the root logger to the lowest level needed and let handler-level thresholds control console vs OTLP, or add a dedicated `otlp_log_level` config.

**Definition of Done.**
- In prod config, an INFO log is delivered to the OTLP exporter (asserted via in-memory log exporter) while console honors WARN.

**Deliverable.** Level plumbing in `logging_config.py`/`config.py` + test.

### F9. `scrub_dict` does not recurse into lists

**Description.**
`{"items": [{"password": ...}]}` leaks because `scrub_dict` recurses into dicts but not lists.

**What is needed.**
- Recurse into list/tuple elements, applying `scrub_dict` to nested mappings.

**Definition of Done.**
- A test with nested-list PII asserts full redaction.

**Deliverable.** Updated `scrub_dict` + test.

---

## Deferred (not blocking GA)

- `kafka-propagation` — native Kafka trace-context propagation (nice-to-have).
- `sm-integration` — integrate `yaks-observability` into `service-management`.
- `sm-testing` — validate the integration end-to-end.

---

## Global Definition of Done (release gate)

1. F1–F5 complete; F6–F9 complete or explicitly documented-and-accepted.
2. `poetry run task test` green, offline, terminating, coverage target met.
3. `poetry run task lint` clean.
4. No secret (`password`/`authorization`/`token`) present in any exported span, log attribute, or log body — proven by real in-memory exporter tests.
5. `setup(app)` is idempotent.
6. README documents endpoint precedence and the metrics stance.
7. Changes committed on `feature/yaks-observability-ga` with descriptive messages.

## Suggested execution order

F3 fixtures (in-memory + offline) → F1 → F2 → F5 → F4 → F9 → F7 → F8 → F6 → docs → full green suite → commit.
