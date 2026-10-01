from fastapi import FastAPI, Query

from app.anomaly_detector import detect_latency_anomalies
from app.simulator import simulate_requests
from app.storage import read_incidents, read_logs, read_metrics, read_traces


app = FastAPI(
    title="RCA'd Observability Platform",
    description="AI-driven observability platform with root cause analysis",
    version="0.1.0"
)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "rcad-api"
    }


@app.post("/simulate")
def simulate(count: int = Query(default=1, ge=1, le=100)):
    results = simulate_requests(count)

    return {
        "message": "Simulation completed",
        "requests_simulated": count,
        "results": results
    }


@app.get("/logs")
def get_logs(
    limit: int = Query(default=20, ge=1, le=500),
    service_name: str | None = None,
    level: str | None = None,
    trace_id: str | None = None
):
    logs = read_logs()

    if service_name:
        logs = [log for log in logs if log.get("service_name") == service_name]

    if level:
        logs = [log for log in logs if log.get("level") == level]

    if trace_id:
        logs = [log for log in logs if log.get("trace_id") == trace_id]

    return {
        "count": min(limit, len(logs)),
        "logs": logs[-limit:]
    }


@app.get("/metrics")
def get_metrics(
    limit: int = Query(default=20, ge=1, le=500),
    service_name: str | None = None,
    metric_name: str | None = None,
    unit: str | None = None
):
    metrics = read_metrics()

    if service_name:
        metrics = [metric for metric in metrics if metric.get("service_name") == service_name]

    if metric_name:
        metrics = [metric for metric in metrics if metric.get("metric_name") == metric_name]

    if unit:
        metrics = [metric for metric in metrics if metric.get("unit") == unit]

    return {
        "count": min(limit, len(metrics)),
        "metrics": metrics[-limit:]
    }


@app.get("/traces")
def get_traces(
    limit: int = Query(default=20, ge=1, le=500),
    trace_id: str | None = None,
    service_name: str | None = None,
    status: str | None = None,
    operation: str | None = None
):
    traces = read_traces()

    if trace_id:
        traces = [trace for trace in traces if trace.get("trace_id") == trace_id]

    if service_name:
        traces = [trace for trace in traces if trace.get("service_name") == service_name]

    if status:
        traces = [trace for trace in traces if trace.get("status") == status]

    if operation:
        traces = [trace for trace in traces if trace.get("operation") == operation]

    return {
        "count": min(limit, len(traces)),
        "traces": traces[-limit:]
    }


@app.post("/detect/anomalies")
def detect_anomalies():
    incidents = detect_latency_anomalies()

    return {
        "message": "Anomaly detection completed",
        "incidents_created": len(incidents),
        "incidents": incidents
    }


@app.get("/incidents")
def get_incidents(
    limit: int = Query(default=20, ge=1, le=500),
    service_name: str | None = None,
    severity: str | None = None,
    status: str | None = None
):
    incidents = read_incidents()

    if service_name:
        incidents = [
            incident for incident in incidents
            if incident.get("service_name") == service_name
        ]

    if severity:
        incidents = [
            incident for incident in incidents
            if incident.get("severity") == severity
        ]

    if status:
        incidents = [
            incident for incident in incidents
            if incident.get("status") == status
        ]

    return {
        "count": min(limit, len(incidents)),
        "incidents": incidents[-limit:]
    }


@app.get("/telemetry/summary")
def telemetry_summary():
    logs = read_logs()
    metrics = read_metrics()
    traces = read_traces()
    incidents = read_incidents()

    error_logs = [log for log in logs if log.get("level") == "ERROR"]
    failed_traces = [trace for trace in traces if trace.get("status") == "error"]

    services = set()

    for log in logs:
        services.add(log.get("service_name"))

    for metric in metrics:
        services.add(metric.get("service_name"))

    for trace in traces:
        services.add(trace.get("service_name"))

    services.discard(None)

    return {
        "total_logs": len(logs),
        "total_metrics": len(metrics),
        "total_traces": len(traces),
        "total_incidents": len(incidents),
        "error_logs": len(error_logs),
        "failed_trace_spans": len(failed_traces),
        "services_observed": sorted(services)
    }