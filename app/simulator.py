import random
import uuid
from typing import List

from app.kafka_producer import (
    flush_events,
    publish_log_event,
    publish_metric_event,
    publish_trace_event,
)
from app.telemetry_schema import LogEvent, MetricEvent, TraceEvent, current_timestamp


SERVICES = [
    "frontend-service",
    "order-service",
    "payment-service",
]


def generate_span_id() -> str:
    return f"span-{uuid.uuid4()}"


def generate_trace_id() -> str:
    return f"trace-{uuid.uuid4()}"


def create_log(service_name: str, level: str, message: str, trace_id: str) -> None:
    log = LogEvent(
        timestamp=current_timestamp(),
        service_name=service_name,
        level=level,
        message=message,
        trace_id=trace_id
    )

    publish_log_event(log.model_dump())


def create_metric(service_name: str, metric_name: str, value: float, unit: str) -> None:
    metric = MetricEvent(
        timestamp=current_timestamp(),
        service_name=service_name,
        metric_name=metric_name,
        value=value,
        unit=unit
    )

    publish_metric_event(metric.model_dump())


def create_trace(
    trace_id: str,
    span_id: str,
    parent_span_id: str | None,
    service_name: str,
    operation: str,
    duration_ms: float,
    status: str
) -> None:
    trace = TraceEvent(
        timestamp=current_timestamp(),
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        service_name=service_name,
        operation=operation,
        duration_ms=duration_ms,
        status=status
    )

    publish_trace_event(trace.model_dump())


def simulate_request() -> dict:
    trace_id = generate_trace_id()

    frontend_span_id = generate_span_id()
    order_span_id = generate_span_id()
    payment_span_id = generate_span_id()

    failure_type = random.choices(
        ["none", "payment_timeout", "payment_error", "order_error"],
        weights=[75, 10, 10, 5],
        k=1
    )[0]

    frontend_latency = random.uniform(20, 80)
    order_latency = random.uniform(50, 180)
    payment_latency = random.uniform(100, 300)

    status = "success"

    if failure_type == "payment_timeout":
        payment_latency = random.uniform(2000, 4000)
        status = "error"
    elif failure_type == "payment_error":
        payment_latency = random.uniform(300, 700)
        status = "error"
    elif failure_type == "order_error":
        order_latency = random.uniform(500, 1200)
        status = "error"

    create_log(
        "frontend-service",
        "INFO",
        "Received checkout request",
        trace_id
    )

    create_trace(
        trace_id,
        frontend_span_id,
        None,
        "frontend-service",
        "POST /checkout",
        frontend_latency,
        "success" if status == "success" else "error"
    )

    create_metric(
        "frontend-service",
        "latency_ms",
        frontend_latency,
        "ms"
    )

    create_log(
        "order-service",
        "INFO" if failure_type != "order_error" else "ERROR",
        "Order created successfully" if failure_type != "order_error" else "Order creation failed",
        trace_id
    )

    create_trace(
        trace_id,
        order_span_id,
        frontend_span_id,
        "order-service",
        "create_order",
        order_latency,
        "success" if failure_type != "order_error" else "error"
    )

    create_metric(
        "order-service",
        "latency_ms",
        order_latency,
        "ms"
    )

    if failure_type == "payment_timeout":
        payment_message = "Payment failed due to bank timeout"
        payment_level = "ERROR"
    elif failure_type == "payment_error":
        payment_message = "Payment failed due to payment gateway error"
        payment_level = "ERROR"
    else:
        payment_message = "Payment processed successfully"
        payment_level = "INFO"

    create_log(
        "payment-service",
        payment_level,
        payment_message,
        trace_id
    )

    create_trace(
        trace_id,
        payment_span_id,
        order_span_id,
        "payment-service",
        "charge_payment",
        payment_latency,
        "success" if failure_type == "none" else "error"
    )

    create_metric(
        "payment-service",
        "latency_ms",
        payment_latency,
        "ms"
    )

    return {
        "trace_id": trace_id,
        "status": status,
        "failure_type": failure_type,
        "services": SERVICES
    }


def simulate_requests(count: int) -> List[dict]:
    results = []

    for _ in range(count):
        result = simulate_request()
        results.append(result)

    flush_events()

    return results