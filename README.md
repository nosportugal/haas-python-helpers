# HaaS Python Helpers

Python packages for automation development and service observability.

## Available Packages

### `otel_log_wrapper`

Configure Python logging to export logs to an OpenTelemetry (OTLP) endpoint. Supports Python 3.10 and later.

[Package documentation](otel_log_wrapper/README.md)

### `sync_confluence`

Sync a Markdown documentation directory or file list to Confluence Cloud as pages and folders. Includes Markdown conversion, image attachments, and a command-line interface. Supports Python 3.11 and later.

[Package documentation](sync_confluence/README.md)

### `yaks_observability`

Add OpenTelemetry logs, traces, and metrics to FastAPI applications, with automatic request instrumentation, environment-aware configuration, and PII redaction. Optional downstream instrumentation is available for SQLAlchemy, httpx, and requests. Supports Python 3.11 and later.

[Package documentation](yaks_observability/README.md)
