# Team Onboarding — yaks-observability

## What is this?

`yaks-observability` is our shared observability package. Drop it into any FastAPI app and get **structured logs + traces + metrics** with one line.

## Quick Start for Existing Apps

### 1. Add dependency

```bash
poetry add yaks-observability
```

With downstream instrumentation (SQLAlchemy, httpx, requests):

```bash
poetry add "yaks-observability[downstream]"
```

### 2. Wire into main.py

```python
from fastapi import FastAPI
from yaks_observability import setup

app = FastAPI()
setup(app)
```

### 3. Set environment variables

| Variable | Default | Overrideable | Description |
|----------|---------|-------------|-------------|
| `ENVIRONMENT_TYPE` | `dev` | — | `dev`, `qa`, `prod`, `testing` |
| `OTEL_SERVICE_NAME` | *(required for prod)* | — | Service identifier in all OTLP signals |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4318` | — | OTLP collector base URL |
| `OTEL_TRACES_SAMPLER_ARG` | `1.0` (dev), `0.1` (prod) | — | Sampling ratio 0.0–1.0 |
| `OTEL_HEALTH_ENDPOINTS` | `/health,/readiness,/liveness,/metrics,/healthz` | ✅ Comma-list | Paths suppressed from access logs & spans |
| `OTEL_ENABLE_PII_REDACTION` | `true` | `true`/`false` | Scrub sensitive data before export & console |
| `OTEL_ENABLE_CONSOLE_JSON` | `false` | `true`/`false` | Force JSON formatting on stdout |

### 4. That's it — no route changes

All routes are auto-traced. Health checks are filtered. Logs are structured JSON in production.

## What Changes for Developers?

**Nothing**, mostly. The package is zero-config for the happy path.

If you need custom spans:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("process_order") as span:
    span.set_attribute("order.id", order_id)
    # business logic
```

## Testing Against OTEL

Use `ENVIRONMENT_TYPE=testing` in your tests — it disables OTLP export and keeps everything local.

## Setup Ordering

Call `setup(app)` **before** `uvicorn` starts:

```python
from fastapi import FastAPI
from yaks_observability import setup

app = FastAPI()
setup(app)  # MUST be before uvicorn.run / server startup
```

Wrong ordering (lifespan already active) prevents OTEL providers from being registered for graceful shutdown.

## PII Redaction Scope

`OTEL_ENABLE_PII_REDACTION=true` (default) scrubs sensitive data from **both**:

1. **OTLP export** — redacted before leaving the app.
2. **Console/stdout** — redacted before printing to the terminal/file.

> **Limitation:** Redaction is regex-based. Novel formats or heavily obfuscated secrets may leak. Treat it as a safety net, not a guarantee.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "No spans in backend" | Check `OTEL_EXPORTER_OTLP_ENDPOINT` is reachable, env is not `testing` |
| "High log volume" | Normal in dev (`DEBUG`). Prod uses `WARN` + sampling. |
| "Health checks still logged" | Ensure `setup(app)` is called **before** `uvicorn` starts |
| "Collector down → app hangs" | Fixed in v1.0.0 — app now shuts down gracefully even if OTLP is unreachable |

## Rollout Checklist

- [ ] Add `yaks-observability` to app's `pyproject.toml`
- [ ] Add `setup(app)` call in `main.py`
- [ ] Configure `OTEL_SERVICE_NAME` in deployment env
- [ ] Verify OTLP endpoint is reachable from the app's network
- [ ] Validate traces appear in your OTLP backend (e.g. Grafana Tempo, Jaeger)
