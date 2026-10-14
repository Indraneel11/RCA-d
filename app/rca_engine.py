from datetime import datetime, timedelta, timezone
from typing import Dict, List

from app.service_graph import correlate_failed_calls
from app.storage import read_incidents, read_logs, read_metrics, read_traces


def parse_timestamp(timestamp: str) -> datetime | None:
    if not timestamp:
        return None

    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def filter_by_time_window(events: List[Dict], minutes: int | None) -> List[Dict]:
    if minutes is None:
        return events

    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    filtered_events = []

    for event in events:
        event_time = parse_timestamp(event.get("timestamp"))

        if event_time is None:
            continue

        if event_time >= cutoff_time:
            filtered_events.append(event)

    return filtered_events


def get_confidence(score: int) -> str:
    if score >= 10:
        return "HIGH"

    if score >= 5:
        return "MEDIUM"

    return "LOW"


def analyze_root_causes(
    minutes: int | None = None,
    trace_id: str | None = None,
) -> Dict:
    incidents = filter_by_time_window(read_incidents(), minutes)
    logs = filter_by_time_window(read_logs(), minutes)
    metrics = filter_by_time_window(read_metrics(), minutes)
    traces = filter_by_time_window(read_traces(), minutes)

    if trace_id is not None:
        logs = [
            log for log in logs
            if log.get("trace_id") == trace_id
        ]

        traces = [
            span for span in traces
            if span.get("trace_id") == trace_id
        ]

        incidents = [
            incident for incident in incidents
            if incident.get("trace_id") == trace_id
            or (incident.get("evidence") or {}).get("trace_id") == trace_id
        ]

        metrics = [
            metric for metric in metrics
            if metric.get("trace_id") == trace_id
        ]

    service_scores = {}

    def ensure_service(service_name: str) -> None:
        if service_name not in service_scores:
            service_scores[service_name] = {
                "service_name": service_name,
                "score": 0,
                "base_score": 0,
                "graph_bonus": 0,
                "confidence": "LOW",
                "reasons": [],
                "evidence": {
                    "incident_count": 0,
                    "error_log_count": 0,
                    "failed_trace_count": 0,
                    "high_latency_metric_count": 0,
                    "correlated_trace_count": 0,
                    "upstream_failed_services": [],
                },
            }

    for incident in incidents:
        service_name = incident.get("service_name")
        severity = incident.get("severity")
        anomaly_type = incident.get("anomaly_type")

        if not service_name:
            continue

        ensure_service(service_name)
        candidate = service_scores[service_name]
        candidate["evidence"]["incident_count"] += 1

        if severity == "HIGH":
            candidate["score"] += 3
            candidate["reasons"].append(
                f"HIGH severity incident detected: {anomaly_type}"
            )
        elif severity == "MEDIUM":
            candidate["score"] += 2
            candidate["reasons"].append(
                f"MEDIUM severity incident detected: {anomaly_type}"
            )
        else:
            candidate["score"] += 1
            candidate["reasons"].append(
                f"Incident detected: {anomaly_type}"
            )

    # Match ERROR logs to failed spans from the same service and trace.
    failed_trace_keys = {
        (trace.get("service_name"), trace.get("trace_id"))
        for trace in traces
        if trace.get("status") == "error"
        and trace.get("service_name")
        and trace.get("trace_id")
    }

    scored_error_trace_keys = set()

    for log in logs:
        service_name = log.get("service_name")
        level = log.get("level")
        message = log.get("message")

        if not service_name or level != "ERROR":
            continue

        ensure_service(service_name)
        candidate = service_scores[service_name]

        # Count every ERROR log as evidence, even if scoring is deduplicated.
        candidate["evidence"]["error_log_count"] += 1

        log_trace_id = log.get("trace_id")
        log_key = (service_name, log_trace_id)

        # Repeated ERROR logs from one service in one trace contribute
        # only one scoring signal.
        if log_trace_id:
            if log_key in scored_error_trace_keys:
                continue

            scored_error_trace_keys.add(log_key)

        correlated = (
            bool(log_trace_id)
            and log_key in failed_trace_keys
        )
        points = 3 if correlated else 1

        candidate["score"] += points
        candidate["reasons"].append(
            f"{'Trace-correlated' if correlated else 'Uncorrelated'} "
            f"ERROR log found: {message}"
        )

    for trace in traces:
        service_name = trace.get("service_name")
        status = trace.get("status")
        operation = trace.get("operation")

        if not service_name or status != "error":
            continue

        ensure_service(service_name)
        candidate = service_scores[service_name]

        candidate["score"] += 3
        candidate["evidence"]["failed_trace_count"] += 1
        candidate["reasons"].append(
            f"Failed trace span found during operation: {operation}"
        )

    for metric in metrics:
        service_name = metric.get("service_name")
        metric_name = metric.get("metric_name")
        value = metric.get("value")

        if not service_name or metric_name != "latency_ms" or value is None:
            continue

        if value <= 1000:
            continue

        ensure_service(service_name)
        candidate = service_scores[service_name]

        if value >= 2000:
            candidate["score"] += 3
        else:
            candidate["score"] += 2

        candidate["evidence"]["high_latency_metric_count"] += 1
        candidate["reasons"].append(
            f"High latency metric found: {value:.2f}ms"
        )

    graph_evidence = correlate_failed_calls(traces)

    for service_name, evidence in graph_evidence.items():
        if service_name not in service_scores:
            continue

        candidate = service_scores[service_name]
        candidate["base_score"] = candidate["score"]
        candidate["graph_bonus"] = evidence["graph_bonus"]
        candidate["score"] += evidence["graph_bonus"]

        candidate["evidence"]["correlated_trace_count"] = (
            evidence["correlated_trace_count"]
        )
        candidate["evidence"]["upstream_failed_services"] = (
            evidence["upstream_failed_services"]
        )

        candidate["reasons"].insert(
            0,
            "Failed call chain observed from "
            + ", ".join(evidence["upstream_failed_services"])
            + f" in {evidence['correlated_trace_count']} trace(s)",
        )

    root_causes = list(service_scores.values())

    for root_cause in root_causes:
        if root_cause["graph_bonus"] == 0:
            root_cause["base_score"] = root_cause["score"]

        root_cause["confidence"] = get_confidence(root_cause["score"])

        unique_reasons = []

        for reason in root_cause["reasons"]:
            if reason not in unique_reasons:
                unique_reasons.append(reason)

        root_cause["reasons"] = unique_reasons[:10]

    root_causes.sort(
        key=lambda item: (
            item["score"],
            len(item["evidence"]["upstream_failed_services"]),
        ),
        reverse=True,
    )

    return {
        "message": "RCA analysis completed",
        "time_window_minutes": minutes,
        "trace_id": trace_id,
        "events_analyzed": {
            "incidents": len(incidents),
            "logs": len(logs),
            "metrics": len(metrics),
            "traces": len(traces),
        },
        "services_analyzed": len(root_causes),
        "top_root_causes": root_causes[:3],
    }