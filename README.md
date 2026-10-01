# RCA'd

RCA'd is an AI-driven observability platform with root cause analysis.

## Phase 1

This phase implements a local telemetry simulator and API.

### Features

- Simulates frontend, order, and payment services
- Generates structured logs
- Generates metrics
- Generates trace spans
- Simulates normal and failure scenarios
- Stores telemetry in JSONL files
- Exposes telemetry through FastAPI endpoints

### Run

```bash
uvicorn app.main:app --reload