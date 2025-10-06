# Observability

## Key Metrics (per route & global)
- **Availability**: 2xx rate, 5xx rate
- **Latency**: p50 / p95 / p99 (server timing or gateway traces)
- **Rate limiting**: 429 rate, quota utilisation
- **Throughput**: Requests per second (RPS)
- **Dependency health**: DB latency / error rate, external calls
- **Saturation**: worker queue depth, CPU, memory

## Suggested GA SLOs
- **Availability**: 99.9% monthly (error budget ~43m 49s)
- **Latency**: p95 < 300 ms (reads), p95 < 500 ms (writes)
- **Rate limit correctness**: <0.1% incorrect 429 over 7 days

## Dashboards
1. **API Overview**: 2xx/4xx/5xx %, p95 latency, RPS, 429 rate, Top endpoints
2. **Endpoint Drilldown**: per route p95/p99, 5xx %, recent deploy markers
3. **Dependencies**: DB p95 & errors, connection pool usage; External HTTP p95/error rate

### Import dashboards
An initial vendor‑agnostic starter file lives at `observability/dashboards.json`.

Steps:
1. Import / load the JSON in your metrics UI (Grafana / custom) mapping metric names:
	- Histogram: `api.request_latency_ms`
	- Counter: `api.requests`
	- HTTP status counter: (e.g. `http_requests_total{status="..."}`) or OTLP equivalent with `status_code` label
2. Adjust selectors for `service.name` and `deployment.environment` variables (defaults: `api`, `prod`).
3. Set alert ideas:
	- p95 latency: >300ms (read) / >500ms (write) sustained 5–10m
	- 5xx rate: >1% over 5m
	- 429 rate: >5% over 10m (investigate throttling fairness)
4. Tune thresholds per panel to match real baseline before enforcing strict paging.
5. Commit any stack‑specific transformations (e.g. rename labels) in a copy if needed.

### Alerts examples
Pseudo rules (adjust for tooling syntax):
```
# Latency (read endpoints) page
IF p95(api.request_latency_ms{route_type="read",service.name="api"}) > 600ms FOR 10m THEN page

# 5xx rate warn → page
IF (rate(http_requests_total{status=~"5..",service.name="api"}[5m]) / rate(http_requests_total{service.name="api"}[5m])) * 100 > 1 FOR 5m THEN page

# 429 spike investigation (no immediate page)
IF (rate(http_requests_total{status="429",service.name="api"}[10m]) / rate(http_requests_total{service.name="api"}[10m])) * 100 > 5 FOR 10m THEN create ticket
```


## Alerting Thresholds (initial)
| Signal | Warn | Page |
|--------|------|------|
| 5xx rate | >0.5% 5m | >1% 5m |
| p95 latency (read) | >450 ms 10m | >600 ms 10m |
| p95 latency (write) | >750 ms 10m | >1000 ms 10m |
| 429 rate | >5% 10m | (Investigative) |
| DB error rate | >0.2% 5m | >0.5% 5m |
| Post-deploy 5xx | — | >2% within 10m of deploy |

## Logging & Correlation
- Include `request_id`, `tenant_id`, `user_id`, `duration_ms`, `path`, `status` in structured JSON log lines.
- Correlate RFC 7807 `instance` (when provided) with `request_id`.
- Avoid plaintext secrets; filter tokens and credentials.

## Tracing
- Adopt W3C TraceContext headers (`traceparent`, `tracestate`).
- Instrument DB calls and external HTTP clients; tag spans with `tenant_id` and outcome.

## Runbooks (stubs)
### Rate limit incident
1. Confirm elevated 429 via dashboard.
2. Inspect `status/api_status.json` badge status (changed vs stable).
3. Adjust limit registry (temporary increase) or identify abusive client.
4. Communicate in CHANGELOG if permanent policy tweak.

### DB saturation
1. Check connection pool usage & wait events.
2. Increase pool / scale replicas; examine slow queries (EXPLAIN / index add).
3. Reassess ORM patterns (N+1) and add caching if repetitive.

## Next Enhancements
- Add histogram metrics for body size distribution.
- Emit percentiles via OpenTelemetry exporter.
- Synthetic canaries hitting critical endpoints every minute.

## Domain Event Telemetry (Pilot)

During pilot we expose a lightweight counter `yuplan.events_total` (labels: `action`, optional `avdelning`, optional `maltid`) for coarse activity insight without adding DB load. Current instrumented action:

| action | Description | Labels used |
|--------|-------------|-------------|
| `registrering` | User-facing creation action (currently mapped to note creation placeholder) | `avdelning` (if session unit), `maltid` (reserved) |

### Panels Added
Two starter panels appended to `observability/dashboards.json`:

1. `Registreringar per minut` – 1m rate of `yuplan.events_total{action="registrering"}` (short-term spikes).
2. `Registreringar per avdelning (24h)` – Top 5 increase over 24h grouped by `avdelning`.

### PromQL Examples
```
# 1m rate (events/min)
sum(rate(yuplan_events_total{action="registrering",service.name="api"}[1m])) * 60

# Top 5 avdelning last 24h
topk(5, sum by (avdelning)(increase(yuplan_events_total{action="registrering",service.name="api"}[24h])))
```

### Export / Overhead
- Counter increments only when OTEL SDK is present; otherwise functions are no-ops.
- No cardinality explosion expected (bounded set of avdelningar; ensure names are normalized and limited in pilot).

### Future
- Add real domain events (attendance_submit, meal_log, task_complete).
- Derive daily cohorts and funnel metrics in separate analytical pipeline.
