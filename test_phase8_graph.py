import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.rca_engine import analyze_root_causes


class Phase8GraphTest(unittest.TestCase):
    def test_payment_failure_cascade(self):
        now = datetime.now(timezone.utc).isoformat()

        traces = [
            {
                "timestamp": now,
                "trace_id": "test-trace-1",
                "span_id": "frontend-span",
                "parent_span_id": None,
                "service_name": "frontend-service",
                "operation": "POST /checkout",
                "status": "error",
            },
            {
                "timestamp": now,
                "trace_id": "test-trace-1",
                "span_id": "order-span",
                "parent_span_id": "frontend-span",
                "service_name": "order-service",
                "operation": "create_order",
                "status": "error",
            },
            {
                "timestamp": now,
                "trace_id": "test-trace-1",
                "span_id": "payment-span",
                "parent_span_id": "order-span",
                "service_name": "payment-service",
                "operation": "charge_payment",
                "status": "error",
            },
        ]

        with (
            patch("app.rca_engine.read_incidents", return_value=[]),
            patch("app.rca_engine.read_logs", return_value=[]),
            patch("app.rca_engine.read_metrics", return_value=[]),
            patch("app.rca_engine.read_traces", return_value=traces),
        ):
            result = analyze_root_causes(minutes=10)

        ranked = result["top_root_causes"]

        self.assertEqual(
            [item["service_name"] for item in ranked],
            ["payment-service", "order-service", "frontend-service"],
        )
        self.assertEqual(
            [item["graph_bonus"] for item in ranked],
            [4, 2, 0],
        )
        self.assertEqual(
            ranked[0]["score"],
            ranked[0]["base_score"] + ranked[0]["graph_bonus"],
        )


if __name__ == "__main__":
    unittest.main()