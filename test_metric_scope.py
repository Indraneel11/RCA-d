from datetime import datetime, timezone
from unittest.mock import patch

from app.rca_engine import analyze_root_causes


now = datetime.now(timezone.utc).isoformat()

metrics = [
    {
        "timestamp": now,
        "service_name": "payment-service",
        "metric_name": "latency_ms",
        "value": 2500.0,
        "trace_id": "payment-request",
    },
    {
        "timestamp": now,
        "service_name": "auth-service",
        "metric_name": "latency_ms",
        "value": 2300.0,
        "trace_id": "auth-request",
    },
    {
        "timestamp": now,
        "service_name": "payment-service",
        "metric_name": "latency_ms",
        "value": 2800.0,
        # Historical metric: no trace_id.
    },
]

with (
    patch("app.rca_engine.read_incidents", return_value=[]),
    patch("app.rca_engine.read_logs", return_value=[]),
    patch("app.rca_engine.read_metrics", return_value=metrics),
    patch("app.rca_engine.read_traces", return_value=[]),
):
    overall = analyze_root_causes(minutes=10)
    payment = analyze_root_causes(minutes=10, trace_id="payment-request")
    auth = analyze_root_causes(minutes=10, trace_id="auth-request")

assert overall["trace_id"] is None
assert overall["events_analyzed"]["metrics"] == 3

assert payment["events_analyzed"]["metrics"] == 1
assert payment["top_root_causes"][0]["service_name"] == "payment-service"
assert payment["top_root_causes"][0]["score"] == 3

assert auth["events_analyzed"]["metrics"] == 1
assert auth["top_root_causes"][0]["service_name"] == "auth-service"
assert auth["top_root_causes"][0]["score"] == 3

print("Metric trace isolation: PASS")