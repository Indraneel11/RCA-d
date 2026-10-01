import uuid
from typing import Dict, List, Set, Tuple

from app.storage import read_metrics, write_incident
from app.telemetry_schema import current_timestamp


LATENCY_THRESHOLD_MS = 1000


def build_incident_key(service_name: str, metric_name: str, timestamp: str) -> Tuple[str, str, str]:
    return service_name, metric_name, timestamp


def detect_latency_anomalies() -> List[Dict]:
    metrics = read_metrics()
    incidents = []

    seen: Set[Tuple[str, str, str]] = set()

    for metric in metrics:
        service_name = metric.get("service_name")
        metric_name = metric.get("metric_name")
        value = metric.get("value")
        timestamp = metric.get("timestamp")

        if metric_name != "latency_ms":
            continue

        if value is None:
            continue

        if value <= LATENCY_THRESHOLD_MS:
            continue

        incident_key = build_incident_key(
            service_name=service_name,
            metric_name=metric_name,
            timestamp=timestamp
        )

        if incident_key in seen:
            continue

        seen.add(incident_key)

        severity = "HIGH" if value >= 2000 else "MEDIUM"

        incident = {
            "incident_id": f"inc-{uuid.uuid4()}",
            "timestamp": current_timestamp(),
            "source_metric_timestamp": timestamp,
            "service_name": service_name,
            "severity": severity,
            "anomaly_type": "high_latency",
            "metric_name": metric_name,
            "metric_value": value,
            "threshold": LATENCY_THRESHOLD_MS,
            "description": (
                f"High latency detected in {service_name}: "
                f"{value:.2f}ms exceeded threshold of {LATENCY_THRESHOLD_MS}ms"
            ),
            "status": "open"
        }

        write_incident(incident)
        incidents.append(incident)

    return incidents