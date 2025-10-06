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
