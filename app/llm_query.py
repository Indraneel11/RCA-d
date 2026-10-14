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


def build_fallback_answer(context: Dict) -> str:
    rca_explanation = context.get("rca_explanation", {})
    explanation = rca_explanation.get("explanation")
    root_cause_service = rca_explanation.get("root_cause_service")
    confidence = rca_explanation.get("confidence")
    recommended_actions = rca_explanation.get("recommended_actions", [])

    if not explanation:
        return (
            "Gemini is currently unavailable, and RCA'd could not generate a "
            "root cause explanation from the selected time window. Try expanding "
            "the time window or generating fresh telemetry."
        )

    answer = (
        "Gemini is currently unavailable, so RCA'd is returning the "
        "rule-based RCA explanation instead.\n\n"
    )

    if root_cause_service:
        answer += f"Likely root cause: {root_cause_service}\n"

    if confidence:
        answer += f"Confidence: {confidence}\n"

    answer += f"\nExplanation: {explanation}\n"

    if recommended_actions:
        answer += "\nRecommended next checks:\n"

        for action in recommended_actions:
            answer += f"- {action}\n"

    return answer


def answer_observability_question(question: str, minutes: int | None = None) -> Dict:
    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    context = build_observability_context(minutes=minutes)

    if not api_key:
        return {
            "message": "Gemini API key is not configured",
            "model": model_name,
            "question": question,
            "time_window_minutes": minutes,
            "answer_source": "fallback",
            "answer": build_fallback_answer(context),
            "context_used": context,
        }

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
            "answer_source": "gemini",
            "answer": response.text,
            "context_used": context,
        }

    except Exception as error:
        return {
            "message": "Gemini query failed; returned fallback RCA explanation",
            "model": model_name,
            "question": question,
            "time_window_minutes": minutes,
            "answer_source": "fallback",
            "answer": build_fallback_answer(context),
            "error": str(error),
            "context_used": context,
        }