# yaks-observability — Remediation Plan (post-peaky review)

Status: **not GA-ready**. The PII redaction pillar is non-functional for both signals, the committed test suite is red and non-terminating, and programmatic config is partly ignored.

This plan closes every blocker found in the Staff Logging Engineer re-review. Work is ordered by ship-priority. Each item lists **Description**, **What is needed**, **Definition of Done (DoD)**, and **Deliverable**.

---

## Review round 2 (2026-08-10) — F1–F9 verified, new redaction gaps found

**Verified fixed (empirically, against real OTLP wire encoders):**
- F1 span attribute redaction reaches the OTLP wire (`hunter2` absent, `[REDACTED]` present, safe attrs preserved).
- F2 log attribute redaction reaches the real OTLP log wire (secret absent, safe value preserved).
- F3 suite green (88 passed), offline, terminating; no background retries to `:4318`.
- F4 `config.otlp_endpoint` wired; F5 idempotency guards present; F7 dead filter removed; F8 root=DEBUG; F9 list recursion works.
- Note: the log-body test that *looked* like a false green is **legitimate** — the literal `password=hunter2` is masked to `******` by tooling; hex-decoding the file bytes confirms the real secret and correct redaction.

**New findings (still open):**

### G1 (P1, security). `scrub_text` leaks bearer tokens and bare PII in log bodies
`Authorization: Bearer <token>` → `Authorization: [REDACTED] <token>` — only the first
whitespace-delimited token after the separator is redacted; the actual token **survives**.
Bare PII values in free text also leak: `email john@example.com`, `card 4111 1111 1111 1111`,
`iban PT50...`, and space-separated `password is hunter2` all pass through unchanged.
**DoD:** value-shape patterns (JWT/bearer, email, PAN, IBAN) redacted regardless of a
preceding key; `key: value` redacts to end-of-value, not first token. Real-wire test proving
`Authorization: Bearer X` and a bare email/PAN are both `[REDACTED]`.
**Deliverable:** hardened `scrub_text` + tests. (todo `fix-scrub-text-token-leak`)

### G2 (P1, security). Span **event** and **link** attributes are not redacted
`RedactingSpanExporter` overrides only top-level `span.attributes`. Verified: a secret in
`span.add_event("login", {"password": ...})` **leaks to the OTLP wire**. `record_exception`
(the most common event) and link attributes bypass redaction entirely.
**DoD:** exported span events and links carry `[REDACTED]` for seeded secrets; real-wire test.
**Deliverable:** event/link scrubbing in the span proxy. (todo `fix-span-event-link-redaction`)

### G3 (P2, usability/security). Redaction is not tunable and over-redacts
`PIIRedactionProcessor()` is constructed with no args in `instrumentation.py` (lines 98, 161);
`extra_safe_keys` and custom patterns are **unreachable in production** — no config field exists.
Meanwhile substring matching over-redacts common non-secrets: `prompt_tokens`,
`completion_tokens`, `token_count`, `session_duration`, `email_verified`, `sessionState` are all
`[REDACTED]`. For an AI-heavy org this destroys token-usage observability.
**DoD:** config-driven safe keys / extra patterns wired into both exporters; `token`/`session`/
`email` matches narrowed (e.g. word-boundary or `_count`/`_verified`/`_duration` allow-list);
tests proving `prompt_tokens` is kept and a custom secret key is redacted.
**Deliverable:** config plumbing + narrowed patterns + tests. (todo `fix-redaction-configurable`)

### G4 (P3, note). Metric data-point attributes are not redacted
Only spans and logs are scrubbed. Documented stance acceptable, but state it explicitly so
teams don't record PII as metric attributes.

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

## Review round 3 (2026-08-10) — G1/G3 not actually closed; core claim inverted

The regex-escaping root cause from round 2 was fixed, but empirical re-testing shows
the redaction pillar is still leaking. All findings below are **verified at runtime**,
not read from the source. Ordered by ship-priority.

### H1 (P1, security). G3 body-pattern config is dead code
`PIIRedactionProcessor.__init__` builds `self.body_patterns` (shape + KVP + `extra_body_patterns`),
but **nothing reads it**. `scrub_text` is a `@staticmethod` that only iterates the module
globals `_BODY_SHAPE_PATTERNS` / `_BODY_KEY_VALUE_PATTERNS`. The whole G3 chain
(`OTEL_PII_BODY_PATTERNS → pii_body_patterns → _compile_body_patterns → extra_body_patterns
→ self.body_patterns`) terminates in unused state.
**Verified:** `scrub_text("order CUST-12345 placed")` with `extra_body_patterns=(re.compile(r"CUST-\d+"),)`
returns the string **unchanged** — the custom pattern is ignored.
**Description.** G3 is reported "done" but custom body patterns never reach the scrubber; the
feature is inert in production.
**What is needed.**
- Convert `scrub_text` from `@staticmethod` to an **instance method** that iterates `self.body_patterns`.
- Keep a module-level fallback only if a stateless helper is genuinely needed elsewhere (it is not — the only caller is `RedactingLogExporter._redact_record`, which holds a processor instance).
- Ensure the shape/KVP replacement semantics are preserved (shape → whole-match `[REDACTED]`; KVP → `\1\2[REDACTED]`). Custom `extra_body_patterns` replace the whole match with `[REDACTED]`.
**Definition of Done.**
- `scrub_text` uses instance patterns; `self.body_patterns` is live.
- Test: a processor built with `extra_body_patterns=(CUST-\d+)` redacts `CUST-12345`; a processor without it does not.
- Test: config path `OTEL_PII_BODY_PATTERNS="CUST-\d+"` → exporter redacts a matching body on the real wire.
**Deliverable.** Instance-method `scrub_text` + 2 tests (unit + config-wired). (todo `fix-scrub-text-dead-body-patterns`)

### H2 (P1, security). Deny-list masquerading as allow-list; PII leaks
Module docstring states *"unknown fields are scrubbed by default unless explicitly marked safe"*
(allow-list). `is_safe()` actually returns `True` for any key **not** matching a sensitive term
(deny-list). Classic PII is therefore exported in the clear.
**Verified leaks (`is_safe` returns True):** `full_name`, `address`, `date_of_birth`, `ip_address`, `username`.
**Description.** The documented security posture is the opposite of the implemented one. For a
library distributed to every team app, this silently under-redacts GDPR-relevant PII while the
docstring promises the safe default.
**What is needed (decision required).** A true allow-list is impractical for OTEL spans (it would
strip every semantic-convention attribute: `http.method`, `service.name`, `db.system`, …).
**Recommended:** keep the deny-list model but (a) **correct the docstring** to describe deny-list
behavior honestly, and (b) **expand `_SENSITIVE_KEY_TERMS`** to cover common PII:
`name`/`full[_\-]?name`, `first[_\-]?name`, `last[_\-]?name`, `address`, `dob`/`date[_\-]?of[_\-]?birth`,
`ip`/`ip[_\-]?address`, `nif`/`vat`, `national[_\-]?id`, `passport`, `birthdate`. Guard against
over-redaction (`ip` must not hit `zip`, `description`; `name` must not hit `username` unless intended
— confirm with alpha-boundary tests).
**Definition of Done.**
- Docstring accurately describes deny-list-by-key + shape-based value redaction.
- `full_name`, `address`, `date_of_birth`, `ip_address` are redacted; `service.name`, `http.method`,
  `db.system`, `zip_code`, `description` are preserved.
- Decision recorded in plan (allow-list rejected, rationale documented).
**Deliverable.** Expanded terms + corrected docstring + boundary tests (leak cases + non-over-redaction cases). (todo `fix-denylist-docstring-and-pii-terms`)

### H3 (P1, security). Quoted body values leak
KVP value group `([^"'\s,;]+)` excludes the leading quote, so a quoted secret never matches; it is
also not an email/PAN/JWT, so shape patterns miss it.
**Verified:** `scrub_text('token="abc123xyz"')` → **unchanged**; only `token=abc123xyz` is redacted.
**Description.** Any secret written as `key="value"` or `key='value'` in a log body survives export.
**What is needed.**
- Allow optional surrounding quotes in the KVP pattern: capture `["']?<value>["']?` and redact the
  inner value (or the whole quoted span) to `[REDACTED]`.
- Preserve current unquoted behavior and the `\1\2[REDACTED]` reconstruction.
**Definition of Done.**
- `token="abc"`, `token='abc'`, and `token=abc` all redact the value.
- Non-secret text with quotes is untouched.
**Deliverable.** Revised `_BODY_KEY_VALUE_PATTERNS` + tests for quoted/single-quoted/unquoted. (todo `fix-quoted-body-value-leak`)

### H4 (P2, robustness). Redacting proxies are not real SDK types — no real-wire test
`_RedactedAttributesProxy` / `_RedactedEventProxy` / `_RedactedLinkProxy` delegate via `__getattr__`
but are **not** `ReadableSpan`/`Event`/`Link` instances. Any `isinstance` gate or private
(`span._attributes`) access inside the SDK/OTLP encoder path would break silently. Current tests use
in-memory/mocked exporters only for events/links; no test drives a **real OTLP encoder** over a span
carrying redacted events and links.
**Description.** Latent production risk: redaction "works" in tests but could raise or bypass on the
real OTLP wire depending on encoder internals.
**What is needed.**
- Add a real-wire test that runs a span with an event and a link (each carrying a secret) through the
  actual OTLP encoder (`encode_spans`) and asserts the secret is absent and safe attrs present.
- If the encoder rejects the proxy, switch event/link redaction to construct **real** `Event`/`Link`
  objects (they are constructible) instead of proxies.
**Definition of Done.**
- Real OTLP-encoder test proves event **and** link secrets are `[REDACTED]` on the wire.
- No `isinstance`/private-attr assumption breaks (proven by the encoder test, not mocks).
**Deliverable.** Real-encoder event/link test; proxies replaced with real objects if needed. (todo `fix-proxy-real-wire-events-links`)

### H5 (P2, quality gate). Coverage regressed below the 95 % target
Current suite: **88 passed, 92 % total** (goal 95 %). Under-covered: `pii_redaction.py` 87 %
(event/link scrub + log-body branches), `instrumentation.py` 95 %, `config.py` 96 %.
**What is needed.** Tests covering: event/link scrub helpers, log-body dict vs str vs non-str
branches, `_compile_body_patterns` invalid-regex warning path, `config._parse_comma_list` empty/edge.
**Definition of Done.** `poetry run task test` reports **≥ 95 %** total, offline, terminating.
**Deliverable.** Added tests raising coverage to target. (todo `fix-coverage-regression-95`)

### H6 (P3, hygiene). Stale comments & partial scrubbing
- Comment "Static key-name patterns (substring match)" is stale (now alpha-boundary regex);
  "Standalone auth is omitted" is false (`auth` is in the list).
- `_BUILT_IN_SAFE_KEYS` entry `total_tokens` is redundant (alpha-boundary already spares it).
- `scrub_dict` does not run `scrub_text` over **string values**, nor recurse into nested lists — a
  bearer token inside a safe-keyed string attribute leaks.
**Definition of Done.** Comments corrected; decide (and document) whether string attribute values are
scrubbed via `scrub_text` — recommended for parity with body scrubbing; add a test if implemented.
**Deliverable.** Comment fixes + optional string-value scrubbing + test. (todo `fix-hygiene-and-string-value-scrub`)

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

---

# Review Round 4 (Staff Logging Engineer, runtime-verified)

Scope: re-review after H1–H6. All findings reproduced at runtime against the real
export path (in-memory exporters + real span attributes), not source-read.

**Confirmed fixed:** H1 (scrub_text instance method), H2 (honest deny-list + expanded
terms, `author` spared, `service_name` safe), H3 (quoted values), H4 (real encoder
event+link tests), H5 (95.16%). These are solid.

**New regressions introduced by this round (mostly by H6's `scrub_strings=True` default):**

### I1 (P1). `scrub_strings=True` default corrupts legitimate OTEL attributes on hot path
Verified on real span export:
- `url.full = https://api.example.com/u?ref=US12ABCDE&next=/home&id=42` → `ref=[REDACTED]`
- `db.statement = SELECT * FROM orders WHERE code='AB12CD34'` → `code='[REDACTED]'`
Both are safe-keyed, non-PII attributes. `scrub_dict` (default `scrub_strings=True`) now runs
all body patterns over every string attribute value on the BatchSpanProcessor export thread.
**What is needed.** Default `scrub_strings=False` for structured attribute scrubbing (redact by
KEY only). Keep free-text `scrub_text` for log message **bodies** only (RedactingLogExporter.body).
**Definition of Done.** Real span/log export test proves `url.full`, `db.statement`, `http.target`
pass through byte-identical when the KEY is safe; key-based redaction still works; log string BODY
still scrubbed. **Deliverable.** Default flip + regression test. (todo `fix-scrub-strings-default`)

### I2 (P1). `pattern.groups == 3` heuristic corrupts user 3-group shape patterns
Verified: `extra_body_patterns=(CUST)-(\d+)-(\w+)` on `"CUST-123-ABC"` → `"CUST123[REDACTED]"`
(literal `-` separators dropped). Contradicts documented "shape pattern (whole-match)" contract.
**What is needed.** Remove the group-count heuristic. Track pattern KINDS explicitly:
`self._shape_patterns` (whole-match), `self._kvp_patterns` (group-reconstruct), `self._extra_patterns`
(whole-match). Apply the correct replacement per set.
**Definition of Done.** 3-group user shape pattern redacts whole match without mangling separators;
KVP still reconstructs key+delim. **Deliverable.** Refactor + tests. (todo `fix-pattern-kind-routing`)

### I3 (P2). IBAN shape pattern over-broad and case-sensitive
`\b[A-Z]{2}\d{2}[A-Z0-9]{1,30}\b` redacts `US12ABCDE`, `AB12CD34EF56` (product/trace codes) yet
misses lowercase IBANs. **What is needed.** Tighten to realistic IBAN lengths (country-aware or
15–34 alnum) and/or require an `iban`-adjacent key; accept case-insensitively only in KVP context.
**DoD.** Product codes preserved; canonical IBAN redacted. **Deliverable.** Pattern fix + tests.
(todo `fix-iban-shape-pattern`)

### I4 (P2). Bare `address` term over-redacts OTEL network semconv
Verified `[REDACTED]`: `network.peer.address`, `network.local.address`, `source.address`,
`destination.address`. Only `server.address`/`client.address` were safe-keyed.
**What is needed.** Replace bare `address` with PII-specific forms (`street_address`, `home_address`,
`billing_address`, `postal_address`; `ip_address` already separate) OR add the OTEL network
`*.address` set to `_BUILT_IN_SAFE_KEYS`. **DoD.** Network semconv addresses preserved; postal/home
address redacted. **Deliverable.** Term/safe-key fix + tests. (todo `fix-address-overredaction`)

### I5 (P2). KVP value lookahead ignores `&` (URL query separator)
`email=a@b.com&token=xyz` → entire tail collapsed into one `[REDACTED]`.
**What is needed.** Add `&` to the value-terminator lookahead `(?=\s|$|[,;&])` (mostly mitigated once
I1 stops scrubbing structured attrs, but still affects genuine log bodies containing URLs).
**DoD.** Each query param scrubbed independently. **Deliverable.** Lookahead fix + test.
(todo `fix-kvp-ampersand-boundary`)

### I6 (P3). Empty value emits false redaction signal
`token=` → `token=[REDACTED]` (no secret existed). **What is needed.** Require ≥1 value char
(`([^\r\n]+?)`) so empty values are left untouched. **DoD.** `token=` unchanged; `token=x` redacts.
**Deliverable.** Regex tweak + test. (todo `fix-empty-value-false-signal`)

### I7 (P3). Performance of per-string-value scrubbing
32 regexes × every string attribute on the export thread. Largely resolved by I1 (key-only for
structured attrs). If body scrubbing stays, precompile/cache and short-circuit when no key term
present. **Deliverable.** Note in docs + micro-bench guard. (todo `fix-scrub-perf-note`)

**Suggested order:** I1 → I2 → I4 → I3 → I5 → I6 → I7 → full green + coverage ≥95%.

---

# Review Round 5 (Staff Logging Engineer, runtime-verified)

Scope: full re-review after I1–I7. Confirmed fixed: I1 (safe-keyed `url.full`/`db.statement`
pass byte-identical on real span export), I2 (3-group shape patterns keep separators), I3 (short
product codes spared, canonical IBAN redacted), I4 (`network.*.address` safe, `postal/home/billing`
redacted), I5 (`&` boundary), I6 (`token=` empty untouched). 111 tests green, 95% coverage, lint clean.

New findings, all reproduced at runtime (probe scripts, not source-read). Ordered by ship-priority.

### K1 (P1, security). JSON-string log bodies leak secrets
The single most common structured-logging body — `logger.info(json.dumps(payload))` — is a **string**
of shape `{"password": "abc"}`. The KVP regex `(\bkey\b)(\s*[:=]\s*)` requires the delimiter to
immediately follow the key, but JSON puts a quote there (`"password":`), so no KVP pattern matches.
**Verified leaks:** `{"password": "abc123"}` → unchanged; `{"token":"xyz"}` → unchanged.
**What is needed.** Allow an optional quote between key and delimiter in the KVP key group
(`(\b{t}\b)["']?(\s*[:=]\s*)`), preserving the `\1\2` reconstruction. Add real-wire log tests for
JSON string bodies (dict-dumped and single-quoted).
**DoD.** `{"password":"x"}`, `{'token':'y'}`, and `key="v"` all redact the value; non-secret JSON
untouched. **Deliverable.** KVP regex fix + tests. (todo `fix-json-string-body-leak`)

### K2 (P1, security). `api_key` shape pattern corrupts output AND leaks the value
The bearer/api-key shape regex `\b([Bb]earer|[Aa]pi[_\-]?[Kk]ey)\s*[:=]?\s*([^,;\s]+)` has an
**optional** delimiter and a greedy value class, so on quoted JSON it grabs the wrong span.
**Verified:** `{'api_key': 'k-secret-value'}` → `{'[REDACTED] 'k-secret-value'}` — the output is
mangled and the real secret `k-secret-value` **survives**. This is worse than a plain miss: it emits
a false "redacted" signal while leaking.
**What is needed.** Either (a) require a real delimiter and drop the loose `[^,;\s]+` grab (rely on
the KVP path for `api_key`), or (b) tighten the shape pattern to `Bearer <token>` only (JWT/opaque)
and remove the `api_key` alternation now that KVP + K1 fix cover it.
**DoD.** `{'api_key':'k-secret'}` fully redacts with no residual secret; `Authorization: Bearer <jwt>`
still redacts. **Deliverable.** Shape-pattern fix + tests. (todo `fix-apikey-shape-corruption`)

### K3 (P2, telemetry loss). Provider shutdown skipped on abnormal app exit
FastAPI's default `app.router.lifespan_context` is `_DefaultLifespan` (**never `None`**), so
`attach_lifespan` always takes the `_chained_lifespan` branch. That branch calls
`shutdown_providers(...)` **after `yield` with no `try/finally`**, so any exception raised while the
app is serving skips `force_flush`/`shutdown` → buffered spans, logs, and metrics are lost on crash.
The safe `_managed_lifespan` (which uses `try/finally`) is effectively dead code.
**Verified:** injecting a `RuntimeError` during the chained lifespan yields `shutdown called: 0`.
**What is needed.** Wrap the post-yield shutdown in `try/finally` (or route both paths through a
single `finally`-guarded shutdown). Add a test that raises inside the lifespan and asserts
`shutdown_providers` still runs. **Deliverable.** Lifespan fix + crash-path test. (todo `fix-lifespan-shutdown-on-error`)

### K4 (P3, over-redaction). `token_type` false positive
`token_type=bearer` (OAuth 2.0 standard, non-secret) is `[REDACTED]` because `token` matches.
`grant_type` is correctly spared. **What is needed.** Add `token_type` to `_BUILT_IN_SAFE_KEYS`
(alongside the existing `*_tokens` count keys). **DoD.** `token_type` preserved; `access_token`
still redacted. **Deliverable.** Safe-key add + test. (todo `fix-token-type-safe-key`)

### K5 (P3, hygiene/coverage). `body_patterns` property is dead & untested
The `PIIRedactionProcessor.body_patterns` property (added during I2) has **no production or test
caller** — it is the single uncovered line (`pii_redaction.py:173`). Either wire it where the full
list is genuinely needed or delete it. **Deliverable.** Remove or cover. (todo `fix-dead-body-patterns-property`)

### K6 (P3, dead code). `HealthCheckUrlFilter` is unused in production
`HealthCheckUrlFilter` is never instantiated in `src/` (only its own tests keep it alive). Round-1
F7 removed one dead filter; this twin remains. **What is needed.** Remove it (and its tests) or wire
it as the OTEL-ASGI-attribute fallback it claims to be. **Deliverable.** Delete or wire. (todo `fix-dead-url-filter`)

### K7 (P3, doc). `HealthCheckFilter` prefix/exact-match doc mismatch
`HealthCheckFilter` docstring/comment say "match path prefix", but `_match_health_path` does an
**exact** match after stripping query/trailing slash — so `/health/db` is NOT filtered. Correct the
docstring (exact-match) or switch to real prefix matching if sub-paths must be dropped.
**Deliverable.** Doc fix (or prefix impl) + test. (todo `fix-health-filter-doc`)

**Accepted / not defects (restate, don't fix):**
- Metric data-point attributes remain unredacted (documented G4) — teams must not put PII in metric
  attributes; keep the explicit note.
- Natural-language prose secrets (`the password is hunter2`, no delimiter) are not redacted — inherent
  limitation of regex body scrubbing without NLP; document the boundary.
- `LoggingInstrumentor().instrument(inject_trace_context=True)` — confirmed a **valid** kwarg in the
  pinned version (read via `kwargs.get("inject_trace_context", False)`); trace/span injection works.

**Suggested order:** K1 → K2 → K3 → K4 → K5 → K6 → K7 → full green + coverage ≥95%.

---

## Review Round 5 — Implementation status

All 7 findings implemented and verified:
- **K1** JSON-string body leak fixed via optional quote after key in KVP regex (`["']?`) before delimiter.
- **K2** api_key shape pattern restricted to `Bearer` only (removes `api_key` alternation); no more corruption.
- **K3** `_chained_lifespan` now wrapped in `try/finally` around `yield`; shutdown runs even on exception; crash-path test added.
- **K4** `token_type` added to `_BUILT_IN_SAFE_KEYS`; test added.
- **K5** Dead `body_patterns` property removed.
- **K6** Dead `HealthCheckUrlFilter` class removed; its tests dropped from `test_filters.py`.
- **K7** Health filter docstring corrected (exact match, not prefix); `_match_health_path` doc updated.

**Suite state:** 113 passed, 0 failed. Coverage 96% total, `pii_redaction.py` 100%, `filters.py` 100%. Lint clean.

---

## Review Round 6 — Findings & Remediation Plan

Runtime-verified peaky review after Round-5 fixes. Suite green (113 pass, 96%) and
over-redaction clean (`grant_type`, `token_type`, `http.route`, `content_type`,
`account_number` all preserved). Span attribute AND span-event attribute redaction
verified working at runtime via `RedactingSpanExporter` + `InMemorySpanExporter`.

Three new defects, ALL in the free-text body path (`scrub_text`). The structured
key-based path (`scrub_dict`) — the primary defense for span/log attributes — is
unaffected. Root cause of L1/L2 is shared: the KVP regex models a value as a single
whitespace-delimited token.

### L1 (P1, leak). KVP value truncates at first whitespace → multi-word secret tail leaks
The KVP value lookahead `(?=\s|$|[,;&])` ends the captured value at the first space, so a
secret whose value spans a space leaks the remainder:
- `token: Bearer abc123` → `token: [REDACTED] abc123` (**`abc123` leaks**)
- `secret: my abc123`    → `secret: [REDACTED] abc123` (**`abc123` leaks**)
The Bearer shape pattern no longer rescues this: after Round-5 it requires `Bearer[:=]`
(colon/equals), not `Bearer <token>`, and non-JWT values aren't caught by the JWT shape.
**What's needed.** Make KVP value capture greedy to end-of-segment (up to the next
structural delimiter `,` `;` `}` `]` or line end) instead of stopping at the first space.
Guard against over-consuming across commas in multi-field lines.
**Definition of Done.** `token: Bearer <tok>` and `secret: my <tok>` fully redacted; the
multi-field JSON case (`{"a":"1","password":"p","b":"2"}`) redacts only `p`, leaving `a`/`b`
intact; no regression in the over-redaction sweep. Regression tests added for both.
**Deliverable.** KVP regex/value-capture change in `pii_redaction.py` + tests.
(todo `fix-scrub-text-token-leak`, already open)

### L2 (P1, leak). Nested JSON — sensitive outer key exposes inner value
`{"auth": {"secret": "abc123"}}` → `{"auth: [REDACTED] "abc123"}}`: the sensitive OUTER key
`auth` captures only up to the first inner space (`{"secret":`), leaving `"abc123"` exposed
(**`abc123` leaks**). Same first-whitespace-truncation root cause as L1, exposed through
nesting. (`{"outer": {"password": ...}}` happens to be safe only because `outer` isn't a
sensitive key.)
**What's needed.** Either (a) the L1 greedy-to-delimiter fix must treat `{`/`[` as a value
boundary so a sensitive key whose value is a nested object does NOT swallow the inner keys,
letting the inner sensitive KVP fire on its own; or (b) recursively scrub decoded JSON when a
body parses as JSON. Prefer (a) for the regex path; note (b) as a stronger future option.
**Definition of Done.** `{"auth": {"secret": "<v>"}}` redacts `<v>`; deeply nested
(`{"a":{"b":{"password":"<v>"}}}`) redacts `<v>`; no over-redaction of non-sensitive siblings.
Regression tests for 2- and 3-level nesting.
**Deliverable.** Value-boundary handling in `pii_redaction.py` + tests.

### L3 (P2, corruption — not a leak). JSON string bodies mangled
`{"password": "abc123"}` → `{"password: [REDACTED]`. Two coupled causes: (a) the opening
`["']?` after the key group swallows the key's own closing quote (`password"` becomes
`password:`); (b) value capture consumes the trailing `"}`. No leak, but the surrounding
structure is destroyed (closing quote/brace dropped), which harms log readability and any
downstream JSON parsing of bodies.
**What's needed.** Preserve structural boundary characters: don't let the optional key-quote
or the value capture consume the closing `"`/`}`/`]`. Redaction should replace only the
secret value, leaving delimiters intact: `{"password": "[REDACTED]"}`.
**Definition of Done.** Flat and multi-field JSON bodies keep their closing quotes/braces;
output remains valid-ish JSON shape with values replaced by `[REDACTED]`; no leak regression.
Tests assert exact structurally-preserved output.
**Deliverable.** Regex boundary fix in `pii_redaction.py` + tests.

**Suggested order:** L3 (fix quote/delimiter boundaries) → L1 (greedy-to-delimiter value) →
L2 (nested-object boundary) — they touch the same regex, so land as one coherent change,
then full green + coverage ≥95%.

**Still-open, NON-redaction work (not defects — outstanding scope):**
- `sm-integration` / `sm-testing` — integrating & testing `yaks-observability` into
  service-management is NOT started; this is the largest remaining deliverable.
- `kafka-propagation` — native Kafka trace-context propagation, explicitly a nice-to-have,
  deferred.
- `fix-span-event-link-redaction` — verified working at runtime this round; close it out.

---

## Round 7 — Staff Logging Engineer review (runtime-verified) — RESOLVED

**Context.** Round-6 L1/L2/L3 fixes were reworked (JSON-aware + plain KVP split). This
round re-probed the actual runtime path, found the "complete" claim was premature (build
was red), and fixed all defects. Final state: **122 passed, 96% coverage, ruff clean,
`pii_redaction.py` 100% covered.**

### R7-1 (P1) — build was RED / false completion
`test_scrub_text_ampersand_boundary` failed; prior "36 tests pass" claim was never true
(only 31 tests existed, none L-specific). Ground truth re-established before any further work.

### R7-2 (P1) — double-escaped regex source (two dead patterns)
- Plain KVP boundary class was `[,;&{}\\[\\]\\r\\n]` (raw-f-string `\\` → literal backslash),
  injecting literal `\ [ ] r n` as boundaries (with IGNORECASE, `r`/`n` matched any R/N) while
  real `\r\n` newlines were NOT matched. Caused whole-string consumption.
- JSON numeric branch `\\d+` was literal backslash-d → **numeric secrets never redacted**
  (`{"ssn": 123456789}` leaked).
**Fix.** Corrected to single-escaped `\[\]\r\n` and `\d+`. Added `test_l3_json_numeric_value_redacted`.

### R7-3 (P2) — non-idempotent redaction / doubled placeholders
Shape-patterns-first ordering let plain-KVP re-process inserted `[REDACTED]` (since `[`/`]`
are boundaries): `email=a@b.com&token=…` → `email=[REDACTED]]…`; `Authorization: Bearer eyJ…`
→ `[REDACTED][REDACTED]`.
**Fix.** (a) Reordered `scrub_text`: JSON → plain KVP → shape (structural key redaction
consumes values before shape patterns run). (b) Added `(?!\[REDACTED\])` value guard +
**possessive** delimiter `\s*+[:=]\s*+` (Py 3.11+) so trailing whitespace can't backtrack
and defeat the guard. `scrub_text` is now idempotent. Added `test_scrub_text_is_idempotent`
and two `test_no_doubled_placeholder_*` tests.

### R7-4 (P3, accepted) — numeric JSON value rewrapped in quotes
`{"ssn": 123456789}` → `{"ssn": "[REDACTED]"}`. Still valid JSON, secret removed; type
fidelity sacrificed for a simpler single-replacement. Accepted, documented here.

### Verified clean this round
Multiline value doesn't cross `\n`; `api[_\-]?key` term works via both JSON and plain paths;
20k-char value scrubs in ~1ms (no ReDoS); `author=` not redacted (alpha-boundary intact);
nested/deep JSON, url-query, trailing-comma, non-secret bodies all correct.

**Remaining outstanding scope (unchanged):** `sm-integration`, `sm-testing`, `kafka-propagation`.

---

## Round 8 — Staff Logging Engineer full-package + OTEL best-practices review

Scope widened beyond redaction to the whole package (config, instrumentation, resilience,
logging_config, lifespan, exporters) and OTEL best practices. **Final: 125 passed, 96%
coverage, ruff clean.**

### R8-1 (P1, FIXED) — OTLP exporter timeout used wrong unit
`resilience.get_exporter_kwargs()` returned `timeout=10000` and fed it to the OTLP/HTTP
exporters, whose `timeout` is in **seconds** (`DEFAULT_TIMEOUT = 10  # seconds`). Effective
timeout was **10,000 s (~2.8 h)** for traces, logs, AND metrics — completely defeating the
"fail fast, never block the app thread" resilience goal. A test even enshrined the bug
(`assert timeout == 10000`).
**Fix.** Convert ms→s in `get_exporter_kwargs` (`10_000 ms → 10.0 s`, floor 1 s); updated
tests to assert seconds. Verified `exporter._timeout == 10.0` at runtime.

### R8-2 (P2, FIXED) — Resource missing `service.version` / `service.instance.id`
Resource only had `service.name` + `deployment.environment`. Without `service.version` you
cannot correlate telemetry to a release; without `service.instance.id` you cannot
disambiguate replicas. Both are recommended OTEL resource semconv attributes.
**Fix.** Added `service_version` (`OTEL_SERVICE_VERSION`) and `service_instance_id`
(`OTEL_SERVICE_INSTANCE_ID`, falling back to hostname/pod name) to config + `_build_resource`.
Tests assert both land on the Resource.

### R8-3 (P2, FIXED) — Prod shipped all DEBUG logs over OTLP
The OTLP bridge `LoggingHandler` was hard-pinned to `logging.DEBUG` while root is DEBUG, so
every DEBUG record was exported to the collector even in prod (where `log_level=WARN` only
throttled the console). Log-volume/cost and noise problem.
**Fix.** OTLP handler now uses `config.log_level`, so the env-aware level governs exported
logs too.

### Evaluated, ACCEPTED / follow-up (not changed this round)
- **(P2, follow-up) `LoggingHandler` deprecation.** `opentelemetry-sdk` warns
  `LoggingHandler` is deprecated in favor of the one in `opentelemetry-instrumentation-logging`.
  Functional today; migrate in a dedicated change with focused tests.
- **(P3) Sampler naming.** `always_on`/`always_off` map to `ALWAYS_ON`/`ALWAYS_OFF` (not the
  parent-based variants named in the env string). Behaviourally fine for on/off; ratio path is
  correctly parent-based.
- **(Accepted) Metrics attributes are not PII-redacted.** Documented limitation; metric labels
  should be low-cardinality and non-PII by construction. FastAPIInstrumentor emits templated
  `http.route`, so no high-cardinality path explosion.
- **(Accepted) `OTEL_RESOURCE_ATTRIBUTES`** is parsed by config and also merged by
  `Resource.create`; harmless overlap.
- **Verified healthy:** health-filter exact-match (query/trailing-slash safe), graceful
  degradation swallows optional-dep/collector errors, lifespan chaining shuts providers down
  in `finally`, bounded batch queues (2048/512) drop telemetry (not the app) under backpressure,
  duplicate-handler guards on repeat `setup()`, JSON logs in prod carry `otelTraceID`/`otelSpanID`.

**Remaining outstanding scope (unchanged):** `sm-integration`, `sm-testing`,
`kafka-propagation`, plus the `LoggingHandler` deprecation follow-up.
