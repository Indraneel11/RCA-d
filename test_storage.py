from app.telemetry_schema import LogEvent, MetricEvent, TraceEvent, current_timestamp
from app.storage import write_log_event, write_metric_event, write_trace_event, read_logs, read_metrics, read_traces


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

write_log_event(log.model_dump())
write_metric_event(metric.model_dump())
write_trace_event(trace.model_dump())

print("Logs:", read_logs())
print("Metrics:", read_metrics())
print("Traces:", read_traces())