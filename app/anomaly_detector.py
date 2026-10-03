import uuid
from typing import Dict, List, Set, Tuple

from app.storage import (
    read_incidents,
    read_logs,
    read_metrics,
    read_traces,
    write_incident,
)
from app.telemetry_schema import current_timestamp


LATENCY_THRESHOLD_MS = 1000


def build_existing_incident_keys() -> Set[Tuple[str, str, str]]:
    existing_incidents = read_incidents()
    keys = set()

    for incident in existing_incidents:
        source_event_id = incident.get("source_event_id")
        service_name = incident.get("service_name")
        anomaly_type = incident.get("anomaly_type")

        if source_event_id and service_name and anomaly_type:
            keys.add((source_event_id, service_name, anomaly_type))

    return keys


def create_incident(
    service_name: str,
    severity: str,
    anomaly_type: str,
    source_event_id: str,
    description: str,
    evidence: Dict,
) -> Dict:
    return {
        "incident_id": f"inc-{uuid.uuid4()}",
        "timestamp": current_timestamp(),
        "service_name": service_name,
        "severity": severity,
        "anomaly_type": anomaly_type,
        "source_event_id": source_event_id,
        "description": description,
        "evidence": evidence,
        "status": "open",
    }


def detect_latency_anomalies(existing_keys: Set[Tuple[str, str, str]]) -> List[Dict]:
    metrics = read_metrics()
    incidents = []

    for metric in metrics:
        service_name = metric.get("service_name")
        metric_name = metric.get("metric_name")
        value = metric.get("value")
        timestamp = metric.get("timestamp")

        if metric_name != "latency_ms" or value is None:
            continue

        if value <= LATENCY_THRESHOLD_MS:
            continue

        source_event_id = f"metric:{service_name}:{metric_name}:{timestamp}"
        anomaly_type = "high_latency"
        incident_key = (source_event_id, service_name, anomaly_type)

        if incident_key in existing_keys:
            continue

        severity = "HIGH" if value >= 2000 else "MEDIUM"

        incident = create_incident(
            service_name=service_name,
            severity=severity,
            anomaly_type=anomaly_type,
            source_event_id=source_event_id,
            description=(
                f"High latency detected in {service_name}: "
                f"{value:.2f}ms exceeded threshold of {LATENCY_THRESHOLD_MS}ms"
            ),
            evidence={
                "metric_name": metric_name,
                "metric_value": value,
                "threshold": LATENCY_THRESHOLD_MS,
                "source_metric_timestamp": timestamp,
            },
        )

        write_incident(incident)
        existing_keys.add(incident_key)
        incidents.append(incident)

    return incidents


def detect_error_log_anomalies(existing_keys: Set[Tuple[str, str, str]]) -> List[Dict]:
    logs = read_logs()
    incidents = []

    for log in logs:
        service_name = log.get("service_name")
        level = log.get("level")
        message = log.get("message")
        trace_id = log.get("trace_id")
        timestamp = log.get("timestamp")

        if level != "ERROR":
            continue

        source_event_id = f"log:{service_name}:{trace_id}:{timestamp}"
        anomaly_type = "error_log"
        incident_key = (source_event_id, service_name, anomaly_type)

        if incident_key in existing_keys:
            continue

        incident = create_incident(
            service_name=service_name,
            severity="HIGH",
            anomaly_type=anomaly_type,
            source_event_id=source_event_id,
            description=f"ERROR log detected in {service_name}: {message}",
            evidence={
                "log_level": level,
                "message": message,
                "trace_id": trace_id,
                "source_log_timestamp": timestamp,
            },
        )

        write_incident(incident)
        existing_keys.add(incident_key)
        incidents.append(incident)

    return incidents


def detect_failed_trace_anomalies(existing_keys: Set[Tuple[str, str, str]]) -> List[Dict]:
    traces = read_traces()
    incidents = []

    for trace in traces:
        service_name = trace.get("service_name")
        status = trace.get("status")
        trace_id = trace.get("trace_id")
        span_id = trace.get("span_id")
        operation = trace.get("operation")
        duration_ms = trace.get("duration_ms")
        timestamp = trace.get("timestamp")

        if status != "error":
            continue

        source_event_id = f"trace:{trace_id}:{span_id}:{timestamp}"
        anomaly_type = "failed_trace"
        incident_key = (source_event_id, service_name, anomaly_type)

        if incident_key in existing_keys:
            continue

        incident = create_incident(
            service_name=service_name,
            severity="HIGH",
            anomaly_type=anomaly_type,
            source_event_id=source_event_id,
            description=(
                f"Failed trace span detected in {service_name} "
                f"during operation {operation}"
            ),
            evidence={
                "trace_id": trace_id,
                "span_id": span_id,
                "operation": operation,
                "duration_ms": duration_ms,
                "source_trace_timestamp": timestamp,
            },
        )

        write_incident(incident)
        existing_keys.add(incident_key)
        incidents.append(incident)

    return incidents


def detect_anomalies() -> Dict:
    existing_keys = build_existing_incident_keys()

    latency_incidents = detect_latency_anomalies(existing_keys)
    error_log_incidents = detect_error_log_anomalies(existing_keys)
    failed_trace_incidents = detect_failed_trace_anomalies(existing_keys)

    all_incidents = latency_incidents + error_log_incidents + failed_trace_incidents

    return {
        "incidents_created": len(all_incidents),
        "latency_incidents": len(latency_incidents),
        "error_log_incidents": len(error_log_incidents),
        "failed_trace_incidents": len(failed_trace_incidents),
        "incidents": all_incidents,
    }