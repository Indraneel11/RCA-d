import os
from typing import Dict

from dotenv import load_dotenv
from google import genai

from app.rca_engine import filter_by_time_window
from app.rca_explainer import explain_rca
from app.storage import read_incidents, read_logs, read_metrics, read_traces


load_dotenv()


def build_observability_context(minutes: int | None = None) -> Dict:
    incidents = read_incidents()
    logs = read_logs()
    metrics = read_metrics()
    traces = read_traces()

    incidents = filter_by_time_window(incidents, minutes)
    logs = filter_by_time_window(logs, minutes)
    metrics = filter_by_time_window(metrics, minutes)
    traces = filter_by_time_window(traces, minutes)

    rca_explanation = explain_rca(minutes=minutes)

    latest_incidents = incidents[-5:]

    latest_error_logs = [
        log for log in logs
        if log.get("level") == "ERROR"
    ][-5:]

    latest_failed_traces = [
        trace for trace in traces
        if trace.get("status") == "error"
    ][-5:]

    latest_metrics = metrics[-10:]

    return {
        "time_window_minutes": minutes,
        "telemetry_counts": {
            "logs": len(logs),
            "metrics": len(metrics),
            "traces": len(traces),
            "incidents": len(incidents),
        },
        "rca_explanation": rca_explanation,
        "latest_incidents": latest_incidents,
        "latest_error_logs": latest_error_logs,
        "latest_failed_traces": latest_failed_traces,
        "latest_metrics": latest_metrics,
    }


def answer_observability_question(question: str, minutes: int | None = None) -> Dict:
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return {
            "message": "GEMINI_API_KEY is not configured",
            "answer": (
                "Set GEMINI_API_KEY in your .env file before using "
                "the Gemini query layer."
            ),
        }

    model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    context = build_observability_context(minutes=minutes)

    prompt = f"""
You are an observability assistant for RCA'd, an AI-driven observability platform.

Answer the user's question using only the provided telemetry, incidents, and RCA context.
Do not invent services, incidents, metrics, or root causes that are not present.
If the context is insufficient, say what data is missing.

Your answer should be clear and useful for a software engineer or SRE.

Include:
- likely root cause if available
- supporting evidence
- recommended next checks

User question:
{question}

Observability context:
{context}
"""

    try:
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )

        return {
            "message": "Gemini query completed",
            "model": model_name,
            "question": question,
            "time_window_minutes": minutes,
            "answer": response.text,
            "context_used": context,
        }

    except Exception as error:
        return {
            "message": "Gemini query failed",
            "model": model_name,
            "question": question,
            "time_window_minutes": minutes,
            "error": str(error),
        }