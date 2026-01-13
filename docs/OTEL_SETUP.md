# OpenTelemetry Setup (Python / FastAPI Minimal Guide)

This guide provides a minimal, production-leaning OpenTelemetry (OTel) setup for a Python FastAPI (or Starlette) service covering traces, metrics, logging bridge, and Server-Timing headers.

## 1. Installation

```
pip install \
  opentelemetry-sdk \
  opentelemetry-exporter-otlp \
  opentelemetry-instrumentation-fastapi \
  opentelemetry-instrumentation-requests \
  opentelemetry-instrumentation-logging
```

Optional (local debugging):
```
pip install opentelemetry-exporter-console
```

## 2. Resource Attributes
Attach rich context to all telemetry. Recommended baseline keys:

- `service.name` (from env: `SERVICE_NAME`)
- `service.version` (from env: `SERVICE_VERSION` or package version)
- `deployment.environment` (from env: `DEPLOY_ENV`, e.g. `dev|staging|prod`)
- `team` (from env: `TEAM`)
- `git.sha` (from env: `GIT_SHA` – immutable build/release id)

Example:
```python
from opentelemetry.sdk.resources import Resource
import os
resource = Resource.create({
    "service.name": os.getenv("SERVICE_NAME", "unified-api"),
    "service.version": os.getenv("SERVICE_VERSION", "0.0.0"),
    "deployment.environment": os.getenv("DEPLOY_ENV", "dev"),
    "team": os.getenv("TEAM", "core-platform"),
    "git.sha": os.getenv("GIT_SHA", "unknown"),
})
```

## 3. Tracing
Use OTLP/HTTP exporter + `BatchSpanProcessor`. Default sampling at 1% (traceidratio) – adjustable with env `OTEL_TRACES_SAMPLER_ARG`.

If no explicit sampling env vars are set, assume `OTEL_TRACES_SAMPLER=traceidratio` and `OTEL_TRACES_SAMPLER_ARG=0.01` (≈1% baseline) for controlled cardinality and cost.

```python
import os
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
span_exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")
provider = TracerProvider(resource=resource)
provider.add_span_processor(BatchSpanProcessor(span_exporter))
# Sampler controlled via env: OTEL_TRACES_SAMPLER=traceidratio, OTEL_TRACES_SAMPLER_ARG=0.01
from opentelemetry import trace
trace.set_tracer_provider(provider)
```

## 4. Metrics
Enable OTLP metrics exporter with periodic reader; define key instruments (counter + histogram / gauge). Prefix metrics with `api.` namespace.

```python
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry import metrics

metric_exporter = OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics")
reader = PeriodicExportingMetricReader(metric_exporter)
meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(meter_provider)
meter = metrics.get_meter("api")

api_requests_counter = meter.create_counter("api.requests")
latency_hist = meter.create_histogram("api.request_latency_ms", unit="ms")
```

## 5. Logging Bridge (Optional)
Forward Python logging records into OpenTelemetry (so they may correlate via trace_id & span_id).

```python
import logging
from opentelemetry.instrumentation.logging import LoggingInstrumentation
LoggingInstrumentation(set_logging_format=True)
logging.getLogger().setLevel(logging.INFO)
```

## 6. FastAPI Integration & Server-Timing Header
Instrument framework & outbound calls; expose latency in `Server-Timing` header for quick p95 debugging.

```python
from fastapi import FastAPI, Request, Response
import time
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

app = FastAPI()
FastAPIInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.perf_counter()
    response: Response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    # Update histogram & counter if desired
    latency_hist.record(elapsed_ms, {"route": request.url.path})
    api_requests_counter.add(1, {"route": request.url.path})
    # Server-Timing: key;dur=ms
    response.headers["Server-Timing"] = f"app;dur={elapsed_ms:.2f}"
    return response
```

## 7. Minimal Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `SERVICE_NAME` | Logical service identifier | unified-api |
| `SERVICE_VERSION` | Release / image version | 1.0.0 | 
| `DEPLOY_ENV` | Environment stage | prod |
| `TEAM` | Owning team tag | core-platform |
| `GIT_SHA` | Immutable git commit | a1b2c3d4 |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Collector/Backend OTLP base URL | https://otel-collector:4318 |
| `OTEL_TRACES_SAMPLER` | Sampler type | traceidratio |
| `OTEL_TRACES_SAMPLER_ARG` | Sampler arg (ratio) | 0.01 |
| `OTEL_EXPORTER_OTLP_HEADERS` | (Optional) Auth header(s) | Authorization=Bearer <token> |

## 8. Next Steps Alignment
See `OBSERVABILITY.md` for SLO definitions, dashboards, and alert thresholds.
Add metrics to dashboards: p95 `api.request_latency_ms`, error rate (5xx), request volume trends, saturation signals.
Tag releases with `service.version` and correlate in trace & metric queries.

## Quickstart (FastAPI)

```python
# Copilot: skriv full körbar python-exempel (otel_setup.py eller i appens main.py)
# - import opentelemetry.sdk.resources.Resource
# - from opentelemetry.sdk.trace import TracerProvider
# - from opentelemetry.sdk.trace.export import BatchSpanProcessor
# - from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
# - from opentelemetry.sdk.metrics import MeterProvider
# - from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
# - from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
# - from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
# - from opentelemetry.instrumentation.requests import RequestsInstrumentor
# - histogram: meter.create_histogram("api.request_latency_ms", unit="ms")
# - counter: meter.create_counter("api.requests")
# - middleware: tidstart/tidslut, record histogram, set Server-Timing header
# - app = FastAPI()
# - en GET /health som returnerar {"status":"ok"}

import os, time, logging
from fastapi import FastAPI, Request, Response
from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentation

# 1. Resource
resource = Resource.create({
    "service.name": os.getenv("SERVICE_NAME", "unified-api"),
    "service.version": os.getenv("SERVICE_VERSION", "0.0.0"),
    "deployment.environment": os.getenv("DEPLOY_ENV", "dev"),
    "team": os.getenv("TEAM", "core-platform"),
    "git.sha": os.getenv("GIT_SHA", "unknown"),
})

endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

# 2. Tracing
span_exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")
tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer("api")

# 3. Metrics
metric_exporter = OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics")
reader = PeriodicExportingMetricReader(metric_exporter)
meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(meter_provider)
meter = metrics.get_meter("api")
request_counter = meter.create_counter("api.requests")
latency_hist = meter.create_histogram("api.request_latency_ms", unit="ms")

# 4. Logging bridge (optional)
LoggingInstrumentation(set_logging_format=True)
logging.getLogger().setLevel(logging.INFO)

# 5. FastAPI instrumentation
app = FastAPI()
FastAPIInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

@app.middleware("http")
async def otel_metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response: Response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    route = request.url.path
    latency_hist.record(elapsed_ms, {"route": route})
    request_counter.add(1, {"route": route})
    response.headers["Server-Timing"] = f"app;dur={elapsed_ms:.2f}"
    return response

@app.get("/health")
async def health():
    with tracer.start_as_current_span("health-handler"):
        return {"status": "ok"}

# Run: uvicorn otel_setup:app --reload
```

## Environment Variables (Reference)
```
SERVICE_NAME=unified-api
SERVICE_VERSION=1.0.0
DEPLOY_ENV=prod
TEAM=core-platform
GIT_SHA=abcdef123456
OTEL_EXPORTER_OTLP_ENDPOINT=https://otel-collector:4318
OTEL_TRACES_SAMPLER=traceidratio
OTEL_TRACES_SAMPLER_ARG=0.01
# Optional managed backend auth:
OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer <token>"
```

## Minimal Collector (Optional / Local)

```yaml
# docker-compose.yml snippet
version: "3.9"
services:
  otel-collector:
    image: otel/opentelemetry-collector:latest
    command: ["--config=/etc/otel-config.yaml"]
    ports:
      - "4318:4318"  # OTLP HTTP
    volumes:
      - ./otel-config.yaml:/etc/otel-config.yaml:ro

# otel-config.yaml
receivers:
  otlp:
    protocols:
      http:
exporters:
  logging:
    loglevel: debug
service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [logging]
    metrics:
      receivers: [otlp]
      exporters: [logging]
```

In production swap `logging` exporter for Tempo / Jaeger (traces) and Prometheus / OTLP metrics backend.

## Next Steps
- See `OBSERVABILITY.md` for SLOs, dashboards, and alerting guidance.
- TODO: Create p95 latency dashboard for `api.request_latency_ms`.
- TODO: Alert on 5xx rate threshold (e.g. >2% over 5m).
- TODO: Tag releases with `SERVICE_VERSION` and correlate in traces & metrics.

---

Commit suggestion:
```
docs: add OpenTelemetry setup guide (traces + metrics + Server-Timing)
```
