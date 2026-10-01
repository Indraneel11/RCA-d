from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel


def current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class LogEvent(BaseModel):
    timestamp: str
    service_name: str
    event_type: str = "log"
    level: str
    message: str
    trace_id: str


class MetricEvent(BaseModel):
    timestamp: str
    service_name: str
    event_type: str = "metric"
    metric_name: str
    value: float
    unit: str


class TraceEvent(BaseModel):
    timestamp: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    service_name: str
    event_type: str = "trace"
    operation: str
    duration_ms: float
    status: str