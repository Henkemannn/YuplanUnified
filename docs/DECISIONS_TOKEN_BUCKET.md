# Decisions: Token Bucket Rate Limiting

### 2025-10-02: Rate limiting – retry_after precision & strategy selection

Rationale: Provide fairer distribution under bursty workloads vs fixed window, while keeping observable consistency and simple client semantics.

Key Decisions:
- `retry_after` returneras som heltal sekunder, `ceil`, min 1s, för både fixed window och token bucket.
- Per-limit strategi sätts i registry (`strategy: "fixed" | "token_bucket"`); env `RATE_LIMIT_ALGO` kan sätta global default.
- Token bucket: `burst` defaultar till `quota` om ej satt (full fönsterburst tillåten vid start).
- Metrics: `rate_limit.lookup` inkluderar `strategy`, `rate_limit.hit` inkluderar `strategy`.
- Redis backend används när `RATE_LIMIT_BACKEND=redis` annars memory fallback. Om Redis saknas → memory (test) eller noop för fixed window.
- Tests för Redis token bucket skip:ar om `redis` lib eller server inte finns.

Non-Goals (för denna iteration):
- Exakt retry_after-beräkning för token bucket (placeholder 1s i backend); HTTP-lagret behåller sekunders precision.
- Jitter / backoff randomisering (`RATE_LIMIT_JITTER_MS`) – reserverat för eventuell framtida implementation.

Future Considerations:
- Förbättra `retry_after` i token bucket backends med faktisk deficit-baserad beräkning.
- Per-tenant isolerade redis keyspace prefixes.
- Central config endpoint som listar aktiva strategier per limit.
- Telemetry histogram på token bucket wait times.
