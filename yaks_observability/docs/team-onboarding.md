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

| Variable | What it does |
|----------|-------------|
| `OTEL_SERVICE_NAME` | Your service identifier in traces/metrics |
| `SERVICE_MANAGEMENT_ENVIRONMENT` | `dev`, `qa`, `prod`, `testing` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector URL (e.g. `https://otel.internal`) |
| `OTEL_TRACES_SAMPLER_ARG` | Sampling ratio: `1.0` (dev), `0.1` (prod) |

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

Use `SERVICE_MANAGEMENT_ENVIRONMENT=testing` in your tests — it disables OTLP export and keeps everything local.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "No spans in backend" | Check `OTEL_EXPORTER_OTLP_ENDPOINT` is reachable, env is not `testing` |
| "High log volume" | Normal in dev (`DEBUG`). Prod uses `WARN` + sampling. |
| "Health checks still logged" | Ensure `setup(app)` is called **before** `uvicorn` starts |

## Rollout Checklist

- [ ] Add `yaks-observability` to app's `pyproject.toml`
- [ ] Add `setup(app)` call in `main.py`
- [ ] Configure `OTEL_SERVICE_NAME` in deployment env
- [ ] Verify OTLP endpoint is reachable from the app's network
- [ ] Validate traces appear in your OTLP backend (e.g. Grafana Tempo, Jaeger)
