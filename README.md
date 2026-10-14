# RCA'd

RCA'd is an observability application for investigating service failures. It collects logs, metrics, and distributed traces, detects anomalies, and ranks likely root causes using telemetry evidence and service call relationships.

A web interface brings incidents, request traces, root cause analysis, and observability questions into one workspace.

## Features

- **Telemetry ingestion:** Receives logs, metrics, and trace spans through Kafka.
- **Incident detection:** Identifies error logs, failed spans, and high-latency metrics.
- **Root cause analysis:** Ranks affected services using telemetry signals and observed failed call chains.
- **Trace investigation:** Connects logs, metrics, spans, and RCA results for an individual request.
- **Explanations:** Summarizes evidence and recommends investigation steps.
- **Metric anomaly detection:** Provides Isolation Forest training and detection endpoints.
- **Observability questions:** Answers questions about a selected time window using Gemini when configured, with a rule-based fallback.
- **Web dashboard:** Displays telemetry totals, incidents, failing traces, root cause candidates, and supporting evidence.
- **Telemetry simulator:** Generates checkout traffic and selected failure scenarios for development and testing.

## Architecture

The telemetry pipeline has four main parts:

1. **Producers** publish structured logs, metrics, and traces to Kafka topics.
2. **The consumer** reads Kafka events and stores them in JSONL files.
3. **The analysis services** detect anomalies, correlate traces, and calculate RCA rankings.
4. **FastAPI and React** provide the API and investigation interface.

The included checkout simulator produces telemetry for `frontend-service`, `order-service`, and `payment-service`. Its failure scenarios include payment timeouts, payment gateway errors, and order processing errors.

## Technology

| Component | Technology |
| --- | --- |
| API | FastAPI |
| Frontend | React, TypeScript, Vite |
| Event transport | Apache Kafka |
| Local storage | JSONL |
| Metric anomaly model | scikit-learn Isolation Forest |
| Question answering | Gemini with a rule-based fallback |

## Local installation

### Requirements

- Python 3.10 or newer
- Node.js and npm compatible with the Vite version in `frontend/package.json`
- Docker Desktop with Docker Compose

Run the backend commands from the repository root.

### 1. Install Python dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run backend commands with `.\.venv\Scripts\python.exe` instead of `python`.

### 2. Start Kafka

```powershell
docker compose up -d
docker compose ps
```

The application connects to Kafka at `localhost:9092`.

### 3. Start the telemetry consumer

Open another terminal in the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m app.kafka_consumer
```

Keep the consumer running while telemetry is being published.

### 4. Start the API

Open another terminal in the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

The API is available at [http://127.0.0.1:8000](http://127.0.0.1:8000). Use [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) to explore its endpoints.

### 5. Start the frontend

Open another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). During development, Vite forwards `/api` requests to FastAPI.

## Using the application

### Investigate a failing request

Select a failing trace in the dashboard to view:

- The request path across services
- Logs and metrics associated with the trace ID
- The highest-ranked root cause and its explanation
- The top three root cause candidates and their evidence
- Recommended next checks

### Detect incidents

Select **Run detection** in the incident queue. The detector reads stored telemetry and creates incidents for supported anomaly types. Incidents associated with a trace can open that request directly.

### Ask an observability question

Use the question panel to ask about telemetry and incidents in a selected time window. Questions cover the selected **system-wide time window**; the trace investigation panel is scoped to one request.

To enable Gemini-generated answers, create a `.env` file in the repository root:

```dotenv
GEMINI_API_KEY=your_api_key_here
```

`GEMINI_MODEL` can also be set to select an available model. Without a configured API key, the backend returns a rule-based RCA answer.

### Generate test traffic

The dashboard can generate a selected failure scenario and open its trace when the telemetry arrives. The API also supports direct simulation:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/simulate?count=1&failure_type=payment_timeout"
```

Supported `failure_type` values are `none`, `payment_timeout`, `payment_error`, and `order_error`. Omit the parameter to generate a randomly selected scenario.

## API endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/health` | API health response |
| GET | `/telemetry/summary` | Telemetry totals and observed services |
| GET | `/logs` | Stored logs |
| GET | `/metrics` | Stored metrics |
| GET | `/traces` | Stored trace spans |
| GET | `/incidents` | Stored incidents |
| POST | `/simulate` | Generate test traffic |
| POST | `/detect/anomalies` | Run rule-based anomaly detection |
| POST | `/rca/analyze` | Rank root cause candidates |
| POST | `/rca/explain` | Generate an RCA explanation |
| POST | `/query` | Ask an observability question |
| POST | `/ml/train` | Train the metric anomaly model |
| POST | `/detect/ml-anomalies` | Run ML metric anomaly detection |

Use `trace_id` with `/rca/analyze` or `/rca/explain` to investigate one request. Use `minutes` to restrict an analysis to a recent time window.

## Verification

Run the backend checks from the repository root:

```powershell
python -m compileall -q app
python test_phase8_graph.py
python test_metric_scope.py
python evaluate_rca.py
python evaluate_multi_incident.py
```

Run the frontend checks from `frontend`:

```powershell
npm run build
npm run lint
```

The RCA evaluation scripts use labeled synthetic scenarios to check ranking behavior. Results from those scenarios do not represent accuracy on other workloads.

## Data and configuration

The consumer writes logs, metrics, traces, and incidents to JSONL files in `data/`. The application creates missing data files when storage is accessed.

The repository's `.env` file is ignored by Git. Keep API keys and other credentials out of committed files.