# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

Please open a [GitHub issue](https://github.com/nosportugal/haas-python-helpers/issues)
with the `security` label. For sensitive disclosures, contact the maintainers directly.

## PII & Data Handling

This package includes a **default-deny PII redaction** layer for OpenTelemetry signals.

### What is redacted by default

- Sensitive **keys** in log/span attributes (e.g. `password`, `token`, `email`, `ssn`,
  `iban`, `credit_card`, `nif`, `passport`).
- Sensitive **values** in free-text log message bodies (e.g. bare e-mail addresses,
  JWTs, IBANs, credit-card-like numbers).
- Bearer tokens and API keys in plain key-value or JSON notation.

### What is NOT redacted

- **Raw trace/span attributes** from downstream auto-instrumentors (e.g.
  `url.query` parameters) — these depend on the upstream instrumentor's
  `attributes` map, not on this package.
- **OTEL semantic convention fields** deliberately allow-listed as safe
  (e.g. `server.address`, `client.address`, `network.peer.address`).

### Console vs OTLP

Both stdout (console) and OTLP export paths are redacted when
`OTEL_ENABLE_PII_REDACTION=true` (default). There is **no** separate toggle
for console vs OTLP.

## Known Limitations

1. **PII redaction is regex-based**, not perfect. Novel data formats or heavily
   obfuscated secrets may leak. Treat this as a safety net, not a guarantee.
2. **Health-check log filtering only suppresses `uvicorn.access`**. If your
   application code explicitly `logger.info("/health check ok")` that message
   will still be emitted.
3. **Collector-unreachability resilience**: the app will never crash, but logs
   and spans destined for OTLP will be lost. Console logs remain available.
