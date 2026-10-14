from fastapi import FastAPI, Query
from pydantic import BaseModel

from app.anomaly_detector import detect_anomalies
from app.llm_query import answer_observability_question
from app.ml_detector import detect_ml_metric_anomalies, train_isolation_forest_model
from app.rca_engine import analyze_root_causes
from app.rca_explainer import explain_rca
from app.simulator import FailureType, simulate_requests
from app.storage import read_incidents, read_logs, read_metrics, read_traces


class QueryRequest(BaseModel):
    question: str
    minutes: int | None = None


app = FastAPI(
    title="RCA'd Observability Platform",
    description="AI-driven observability platform with root cause analysis",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "rcad-api",
    }


@app.post("/simulate")
def simulate(
    count: int = Query(default=1, ge=1, le=100),
    failure_type: FailureType | None = Query(default=None),
):
    results = simulate_requests(count, failure_type=failure_type)

    return {
        "message": "Simulation completed",
        "requests_simulated": count,
        "results": results,
    }


@app.post("/ml/train")
def train_ml_model():
    return train_isolation_forest_model()


@app.post("/detect/ml-anomalies")
def run_ml_anomaly_detection():
    return detect_ml_metric_anomalies()


@app.get("/logs")
def get_logs(
    limit: int = Query(default=20, ge=1, le=500),
    service_name: str | None = None,
    level: str | None = None,
    trace_id: str | None = None,
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
        "logs": logs[-limit:],
    }


@app.get("/metrics")
def get_metrics(
    limit: int = Query(default=20, ge=1, le=500),
    service_name: str | None = None,
    metric_name: str | None = None,
    unit: str | None = None,
    trace_id: str | None = None,
):
    metrics = read_metrics()

    if service_name:
        metrics = [
            metric for metric in metrics
            if metric.get("service_name") == service_name
        ]

    if metric_name:
        metrics = [
            metric for metric in metrics
            if metric.get("metric_name") == metric_name
        ]

    if unit:
        metrics = [
            metric for metric in metrics
            if metric.get("unit") == unit
        ]

    if trace_id:
        metrics = [
            metric for metric in metrics
            if metric.get("trace_id") == trace_id
        ]

    return {
        "count": min(limit, len(metrics)),
        "metrics": metrics[-limit:],
    }


@app.get("/traces")
def get_traces(
    limit: int = Query(default=20, ge=1, le=500),
    trace_id: str | None = None,
    service_name: str | None = None,
    status: str | None = None,
    operation: str | None = None,
):
    traces = read_traces()

    if trace_id:
        traces = [
            trace for trace in traces
            if trace.get("trace_id") == trace_id
        ]

    if service_name:
        traces = [
            trace for trace in traces
            if trace.get("service_name") == service_name
        ]

    if status:
        traces = [
            trace for trace in traces
            if trace.get("status") == status
        ]

    if operation:
        traces = [
            trace for trace in traces
            if trace.get("operation") == operation
        ]

    return {
        "count": min(limit, len(traces)),
        "traces": traces[-limit:],
    }


@app.post("/query")
def query_observability(request: QueryRequest):
    return answer_observability_question(
        question=request.question,
        minutes=request.minutes,
    )


@app.post("/detect/anomalies")
def run_anomaly_detection():
    result = detect_anomalies()

    return {
        "message": "Anomaly detection completed",
        **result,
    }


@app.post("/rca/analyze")
def run_rca_analysis(
    minutes: int | None = Query(default=None, ge=1, le=1440),
    trace_id: str | None = None,
):
    return analyze_root_causes(minutes=minutes, trace_id=trace_id)


@app.post("/rca/explain")
def explain_root_cause(
    minutes: int | None = Query(default=None, ge=1, le=1440),
    trace_id: str | None = None,
):
    return explain_rca(minutes=minutes, trace_id=trace_id)


@app.get("/incidents")
def get_incidents(
    limit: int = Query(default=20, ge=1, le=500),
    service_name: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    anomaly_type: str | None = None,
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

    if anomaly_type:
        incidents = [
            incident for incident in incidents
            if incident.get("anomaly_type") == anomaly_type
        ]

    return {
        "count": min(limit, len(incidents)),
        "incidents": incidents[-limit:],
    }


@app.get("/telemetry/summary")
def telemetry_summary():
    logs = read_logs()
    metrics = read_metrics()
    traces = read_traces()
    incidents = read_incidents()

    error_logs = [log for log in logs if log.get("level") == "ERROR"]
    failed_traces = [
        trace for trace in traces
        if trace.get("status") == "error"
    ]

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
        "services_observed": sorted(services),
    }