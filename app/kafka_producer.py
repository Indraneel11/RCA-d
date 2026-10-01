import json
from typing import Any, Dict

from confluent_kafka import Producer


KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"

LOGS_TOPIC = "telemetry.logs"
METRICS_TOPIC = "telemetry.metrics"
TRACES_TOPIC = "telemetry.traces"


producer = Producer({
    "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS
})


def delivery_report(error, message) -> None:
    if error is not None:
        print(f"Failed to deliver message: {error}")
    else:
        print(
            f"Message delivered to {message.topic()} "
            f"[partition {message.partition()}]"
        )


def publish_event(topic: str, event: Dict[str, Any]) -> None:
    producer.produce(
        topic=topic,
        value=json.dumps(event).encode("utf-8"),
        callback=delivery_report
    )

    producer.poll(0)


def publish_log_event(event: Dict[str, Any]) -> None:
    publish_event(LOGS_TOPIC, event)


def publish_metric_event(event: Dict[str, Any]) -> None:
    publish_event(METRICS_TOPIC, event)


def publish_trace_event(event: Dict[str, Any]) -> None:
    publish_event(TRACES_TOPIC, event)


def flush_events() -> None:
    producer.flush()