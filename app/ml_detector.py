import uuid
from pathlib import Path
from typing import Dict, List

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest

from app.storage import read_incidents, read_metrics, write_incident
from app.telemetry_schema import current_timestamp


BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "models"
MODEL_PATH = MODEL_DIR / "isolation_forest.joblib"

MIN_METRICS_FOR_ML = 30
ML_CONTAMINATION_RATE = 0.10


def build_existing_ml_source_ids() -> set:
    existing_incidents = read_incidents()
    source_ids = set()

    for incident in existing_incidents:
        if incident.get("anomaly_type") == "ml_metric_anomaly":
            source_event_id = incident.get("source_event_id")

            if source_event_id:
                source_ids.add(source_event_id)

    return source_ids


def prepare_metric_features(metrics: List[Dict]) -> pd.DataFrame:
    rows = []

    for metric in metrics:
        service_name = metric.get("service_name")
        metric_name = metric.get("metric_name")
        value = metric.get("value")
        timestamp = metric.get("timestamp")

        if service_name is None or metric_name is None or value is None or timestamp is None:
            continue

        rows.append({
            "service_name": service_name,
            "metric_name": metric_name,
            "value": float(value),
            "timestamp": timestamp,
        })

    dataframe = pd.DataFrame(rows)

    if dataframe.empty:
        return dataframe

    dataframe["service_code"] = dataframe["service_name"].astype("category").cat.codes
    dataframe["metric_code"] = dataframe["metric_name"].astype("category").cat.codes

    return dataframe


def get_feature_columns() -> List[str]:
    return [
        "service_code",
        "metric_code",
        "value",
    ]


def train_isolation_forest_model() -> Dict:
    metrics = read_metrics()

    if len(metrics) < MIN_METRICS_FOR_ML:
        return {
            "message": "Not enough metric data to train ML model",
            "minimum_required": MIN_METRICS_FOR_ML,
            "available_metrics": len(metrics),
            "model_trained": False,
        }

    dataframe = prepare_metric_features(metrics)

    if dataframe.empty:
        return {
            "message": "No valid metric rows available for training",
            "model_trained": False,
        }

    features = dataframe[get_feature_columns()]

    model = IsolationForest(
        contamination=ML_CONTAMINATION_RATE,
        random_state=42,
    )

    model.fit(features)

    MODEL_DIR.mkdir(exist_ok=True)

    model_bundle = {
        "model": model,
        "feature_columns": get_feature_columns(),
        "trained_at": current_timestamp(),
        "metrics_used": len(dataframe),
    }

    joblib.dump(model_bundle, MODEL_PATH)

    return {
        "message": "Isolation Forest model trained and saved",
        "model_trained": True,
        "model_path": str(MODEL_PATH),
        "metrics_used": len(dataframe),
        "feature_columns": get_feature_columns(),
    }


def load_model_bundle() -> Dict | None:
    if not MODEL_PATH.exists():
        return None

    return joblib.load(MODEL_PATH)


def create_ml_incident(row: pd.Series, anomaly_score: float) -> Dict:
    service_name = row["service_name"]
    metric_name = row["metric_name"]
    metric_value = float(row["value"])
    timestamp = row["timestamp"]

    source_event_id = f"ml_metric:{service_name}:{metric_name}:{timestamp}"

    return {
        "incident_id": f"inc-{uuid.uuid4()}",
        "timestamp": current_timestamp(),
        "service_name": service_name,
        "severity": "HIGH" if anomaly_score < -0.20 else "MEDIUM",
        "anomaly_type": "ml_metric_anomaly",
        "source_event_id": source_event_id,
        "description": (
            f"ML anomaly detected for {service_name}: "
            f"{metric_name}={metric_value:.2f}"
        ),
        "evidence": {
            "metric_name": metric_name,
            "metric_value": metric_value,
            "source_metric_timestamp": timestamp,
            "ml_model": "IsolationForest",
            "anomaly_score": anomaly_score,
            "model_path": str(MODEL_PATH),
        },
        "status": "open",
    }


def detect_ml_metric_anomalies() -> Dict:
    model_bundle = load_model_bundle()

    if model_bundle is None:
        return {
            "message": "No trained ML model found. Train the model first using POST /ml/train.",
            "incidents_created": 0,
            "incidents": [],
        }

    metrics = read_metrics()

    if len(metrics) < MIN_METRICS_FOR_ML:
        return {
            "message": "Not enough metric data for ML anomaly detection",
            "minimum_required": MIN_METRICS_FOR_ML,
            "available_metrics": len(metrics),
            "incidents_created": 0,
            "incidents": [],
        }

    dataframe = prepare_metric_features(metrics)

    if dataframe.empty:
        return {
            "message": "No valid metric rows available for ML anomaly detection",
            "incidents_created": 0,
            "incidents": [],
        }

    model = model_bundle["model"]
    feature_columns = model_bundle["feature_columns"]

    features = dataframe[feature_columns]

    predictions = model.predict(features)
    scores = model.decision_function(features)

    dataframe["prediction"] = predictions
    dataframe["anomaly_score"] = scores

    anomaly_rows = dataframe[dataframe["prediction"] == -1]

    existing_source_ids = build_existing_ml_source_ids()
    incidents = []

    for _, row in anomaly_rows.iterrows():
        source_event_id = (
            f"ml_metric:{row['service_name']}:"
            f"{row['metric_name']}:{row['timestamp']}"
        )

        if source_event_id in existing_source_ids:
            continue

        incident = create_ml_incident(
            row=row,
            anomaly_score=float(row["anomaly_score"]),
        )

        write_incident(incident)
        existing_source_ids.add(source_event_id)
        incidents.append(incident)

    return {
        "message": "ML anomaly detection completed",
        "model": "IsolationForest",
        "model_trained_at": model_bundle.get("trained_at"),
        "metrics_analyzed": len(dataframe),
        "raw_anomalies_detected": len(anomaly_rows),
        "incidents_created": len(incidents),
        "incidents": incidents,
    }