import json
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

LOGS_FILE = DATA_DIR / "logs.jsonl"
METRICS_FILE = DATA_DIR / "metrics.jsonl"
TRACES_FILE = DATA_DIR / "traces.jsonl"


def ensure_data_files_exist() -> None:
    DATA_DIR.mkdir(exist_ok=True)

    for file_path in [LOGS_FILE, METRICS_FILE, TRACES_FILE]:
        file_path.touch(exist_ok=True)


def append_event(file_path: Path, event: Dict[str, Any]) -> None:
    ensure_data_files_exist()

    with file_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event) + "\n")


def write_log_event(event: Dict[str, Any]) -> None:
    append_event(LOGS_FILE, event)


def write_metric_event(event: Dict[str, Any]) -> None:
    append_event(METRICS_FILE, event)


def write_trace_event(event: Dict[str, Any]) -> None:
    append_event(TRACES_FILE, event)


def read_jsonl(file_path: Path) -> List[Dict[str, Any]]:
    ensure_data_files_exist()

    events = []

    with file_path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                events.append(json.loads(line))

    return events


def read_logs() -> List[Dict[str, Any]]:
    return read_jsonl(LOGS_FILE)


def read_metrics() -> List[Dict[str, Any]]:
    return read_jsonl(METRICS_FILE)


def read_traces() -> List[Dict[str, Any]]:
    return read_jsonl(TRACES_FILE)