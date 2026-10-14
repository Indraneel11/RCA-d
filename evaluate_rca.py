"""Labeled RCA scenarios. Does not write to Kafka or JSONL."""

from datetime import datetime, timezone
from unittest.mock import patch

from app.rca_engine import analyze_root_causes


def trace(timestamp, trace_id, span_id, parent_id, service, status):
    return {
        "timestamp": timestamp,
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_id,
        "service_name": service,
        "status": status,
        "operation": "evaluate",
    }


def error_log(timestamp, service, message, trace_id):
    return {
        "timestamp": timestamp,
        "service_name": service,
        "level": "ERROR",
        "message": message,
        "trace_id": trace_id,
    }


def latency(timestamp, service, value):
    return {
        "timestamp": timestamp,
        "service_name": service,
        "metric_name": "latency_ms",
        "value": value,
    }


def scenarios(timestamp):
    noise = [
        error_log(
            timestamp,
            service,
            "Unrelated transient error",
            f"noise-{service}",
        )
        for service in (
            "auth-service",
            "catalog-service",
            "inventory-service",
        )
    ]

    return [
        {
            "name": "payment_timeout",
            "expected_root": "payment-service",
            "traces": [
                trace(timestamp, "p1", "f", None, "frontend-service", "error"),
                trace(timestamp, "p1", "o", "f", "order-service", "error"),
                trace(timestamp, "p1", "p", "o", "payment-service", "error"),
            ],
            "logs": noise + [
                error_log(timestamp, "payment-service", "Bank timeout", "p1")
            ],
            "metrics": [
                latency(timestamp, "payment-service", 2500)
            ],
        },
        {
            "name": "payment_gateway_error",
            "expected_root": "payment-service",
            "traces": [
                trace(timestamp, "p2", "f", None, "frontend-service", "error"),
                trace(timestamp, "p2", "o", "f", "order-service", "error"),
                trace(timestamp, "p2", "p", "o", "payment-service", "error"),
            ],
            "logs": noise + [
                error_log(timestamp, "payment-service", "Gateway error", "p2")
            ],
            "metrics": [],
        },
        {
            "name": "order_processing_error",
            "expected_root": "order-service",
            "traces": [
                trace(timestamp, "o1", "f", None, "frontend-service", "error"),
                trace(timestamp, "o1", "o", "f", "order-service", "error"),
            ],
            "logs": noise + [
                error_log(
                    timestamp,
                    "order-service",
                    "Order processing failed",
                    "o1",
                )
            ],
            "metrics": [
                latency(timestamp, "order-service", 1200)
            ],
        },
        {
            "name": "frontend_local_error",
            "expected_root": "frontend-service",
            "traces": [
                trace(timestamp, "f1", "f", None, "frontend-service", "error")
            ],
            "logs": noise + [
                error_log(
                    timestamp,
                    "frontend-service",
                    "Frontend exception",
                    "f1",
                )
            ],
            "metrics": [
                latency(timestamp, "frontend-service", 2200)
            ],
        },
        {
            "name": "missing_parent_span",
            "expected_root": "payment-service",
            "traces": [
                trace(
                    timestamp,
                    "p3",
                    "p",
                    "missing",
                    "payment-service",
                    "error",
                )
            ],
            "logs": noise + [
                error_log(timestamp, "payment-service", "Gateway error", "p3")
            ],
            "metrics": [],
        },
        {
            "name": "payment_sparse_with_noisy_auth",
            "expected_root": "payment-service",
            "traces": [
                trace(timestamp, "p4", "f", None, "frontend-service", "error"),
                trace(timestamp, "p4", "o", "f", "order-service", "error"),
                trace(timestamp, "p4", "p", "o", "payment-service", "error"),
            ],
            "logs": noise + [
                error_log(
                    timestamp,
                    "auth-service",
                    "Unrelated retry failure",
                    "noise-auth-service",
                )
                for _ in range(3)
            ],
            "metrics": [],
        },
        {
            "name": "missing_parent_with_noisy_neighbors",
            "expected_root": "payment-service",
            "traces": [
                trace(
                    timestamp,
                    "p5",
                    "p",
                    "missing",
                    "payment-service",
                    "error",
                )
            ],
            "logs": noise + [
                error_log(timestamp, "payment-service", "Gateway error", "p5")
            ] + [
                error_log(
                    timestamp,
                    service,
                    "Unrelated retry failure",
                    f"noise-{service}",
                )
                for service in (
                    "auth-service",
                    "catalog-service",
                    "inventory-service",
                )
                for _ in range(2)
            ],
            "metrics": [],
        },
    ]


def evaluate():
    timestamp = datetime.now(timezone.utc).isoformat()
    cases = scenarios(timestamp)

    top1_hits = 0
    top3_hits = 0

    for case in cases:
        with (
            patch("app.rca_engine.read_incidents", return_value=[]),
            patch("app.rca_engine.read_logs", return_value=case["logs"]),
            patch("app.rca_engine.read_metrics", return_value=case["metrics"]),
            patch("app.rca_engine.read_traces", return_value=case["traces"]),
        ):
            result = analyze_root_causes(minutes=10)

        ranked = [
            item["service_name"]
            for item in result["top_root_causes"]
        ]

        top1_hit = bool(ranked) and ranked[0] == case["expected_root"]
        top3_hit = case["expected_root"] in ranked

        top1_hits += top1_hit
        top3_hits += top3_hit

        print(
            f"{case['name']}: expected={case['expected_root']}, "
            f"top3={ranked}, "
            f"top1={'PASS' if top1_hit else 'FAIL'}, "
            f"top3_hit={'PASS' if top3_hit else 'FAIL'}"
        )

    print(
        f"Top-1 accuracy: "
        f"{top1_hits}/{len(cases)} = {top1_hits / len(cases):.1%}"
    )
    print(
        f"Top-3 accuracy: "
        f"{top3_hits}/{len(cases)} = {top3_hits / len(cases):.1%}"
    )
    print(
        "Synthetic baseline only; these results do not estimate "
        "production accuracy."
    )


if __name__ == "__main__":
    evaluate()