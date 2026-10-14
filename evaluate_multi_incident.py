"""Evaluate RCA when independent failures share a time window."""

from datetime import datetime, timezone
from unittest.mock import patch

from app.rca_engine import analyze_root_causes
from evaluate_rca import error_log, trace


def main():
    now = datetime.now(timezone.utc).isoformat()

    traces = [
        trace(now, "payment-request", "f", None, "frontend-service", "error"),
        trace(now, "payment-request", "o", "f", "order-service", "error"),
        trace(now, "payment-request", "p", "o", "payment-service", "error"),
        trace(now, "auth-request-1", "a1", None, "auth-service", "error"),
        trace(now, "auth-request-2", "a2", None, "auth-service", "error"),
    ]

    logs = [
        error_log(now, "payment-service", "Bank timeout", "payment-request"),
        error_log(now, "auth-service", "Login failure", "auth-request-1"),
        error_log(now, "auth-service", "Login failure", "auth-request-2"),
    ]

    with (
        patch("app.rca_engine.read_incidents", return_value=[]),
        patch("app.rca_engine.read_logs", return_value=logs),
        patch("app.rca_engine.read_metrics", return_value=[]),
        patch("app.rca_engine.read_traces", return_value=traces),
    ):
        overall = analyze_root_causes(minutes=10)
        payment = analyze_root_causes(
            minutes=10,
            trace_id="payment-request",
        )
        auth = analyze_root_causes(
            minutes=10,
            trace_id="auth-request-1",
        )

    def ranked_services(result):
        return [
            candidate["service_name"]
            for candidate in result["top_root_causes"]
        ]

    print("Whole time window:", ranked_services(overall))
    print("Payment trace:", ranked_services(payment))
    print("Auth trace:", ranked_services(auth))

    assert ranked_services(payment)[0] == "payment-service"
    assert ranked_services(auth)[0] == "auth-service"
    assert payment["events_analyzed"]["logs"] == 1
    assert auth["events_analyzed"]["logs"] == 1

    print("Trace-specific RCA checks: PASS")


if __name__ == "__main__":
    main()