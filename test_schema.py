from app.telemetry_schema import LogEvent, MetricEvent, TraceEvent, current_timestamp

log = LogEvent(
    timestamp=current_timestamp(),
    service_name="payment-service",
    level="ERROR",
    message="Payment failed due to bank timeout",
    trace_id="trace-001"
)

metric = MetricEvent(
    timestamp=current_timestamp(),
    service_name="payment-service",
    metric_name="latency_ms",
    value=2500,
    unit="ms"
)

trace = TraceEvent(
    timestamp=current_timestamp(),
    trace_id="trace-001",
    span_id="span-001",
    parent_span_id=None,
    service_name="payment-service",
    operation="charge_payment",
    duration_ms=2500,
    status="error"
)

print(log.model_dump())
print(metric.model_dump())
print(trace.model_dump())