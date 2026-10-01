import json

from confluent_kafka import Consumer

from app.kafka_producer import LOGS_TOPIC, METRICS_TOPIC, TRACES_TOPIC
from app.storage import write_log_event, write_metric_event, write_trace_event


KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"


consumer = Consumer({
    "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
    "group.id": "rcad-telemetry-ingestion",
    "auto.offset.reset": "earliest",
})


def handle_message(topic: str, event: dict) -> None:
    if topic == LOGS_TOPIC:
        write_log_event(event)
    elif topic == METRICS_TOPIC:
        write_metric_event(event)
    elif topic == TRACES_TOPIC:
        write_trace_event(event)
    else:
        print(f"Unknown topic: {topic}")


def consume_events() -> None:
    consumer.subscribe([
        LOGS_TOPIC,
        METRICS_TOPIC,
        TRACES_TOPIC,
    ])

    print("Kafka consumer started. Waiting for telemetry events...")

    try:
        while True:
            message = consumer.poll(timeout=1.0)

            if message is None:
                continue

            if message.error():
                print(f"Consumer error: {message.error()}")
                continue

            topic = message.topic()
            event = json.loads(message.value().decode("utf-8"))

            handle_message(topic, event)

            print(f"Stored event from topic: {topic}")

    except KeyboardInterrupt:
        print("Stopping Kafka consumer...")

    finally:
        consumer.close()


if __name__ == "__main__":
    consume_events()