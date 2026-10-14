from typing import Dict, List

from app.rca_engine import analyze_root_causes


def format_reasons(reasons: List[str]) -> List[str]:
    return reasons[:5]


def count_label(count: int, singular: str, plural: str) -> str:
    label = singular if count == 1 else plural
    return f"{count} {label}"


def build_summary(top_root_cause: Dict) -> str:
    service_name = top_root_cause.get("service_name")
    confidence = top_root_cause.get("confidence")
    score = top_root_cause.get("score")

    return (
        f"The most likely root cause is {service_name}. "
        f"The RCA engine assigned it {confidence} confidence "
        f"with a score of {score}."
    )


def build_evidence_summary(
    top_root_cause: Dict,
    trace_id: str | None = None,
) -> str:
    evidence = top_root_cause.get("evidence", {})

    incident_count = evidence.get("incident_count", 0)
    error_log_count = evidence.get("error_log_count", 0)
    failed_trace_count = evidence.get("failed_trace_count", 0)
    high_latency_metric_count = evidence.get("high_latency_metric_count", 0)
    correlated_trace_count = evidence.get("correlated_trace_count", 0)
    upstream_services = evidence.get("upstream_failed_services", [])

    summary = (
        "Evidence includes "
        f"{count_label(incident_count, 'related incident', 'related incidents')}, "
        f"{count_label(error_log_count, 'ERROR log', 'ERROR logs')}, and "
        f"{count_label(failed_trace_count, 'failed trace span', 'failed trace spans')}."
    )

    summary += (
        " It also includes "
        f"{count_label(high_latency_metric_count, 'high-latency metric', 'high-latency metrics')}."
    )

    if correlated_trace_count and upstream_services:
        summary += (
            f" {count_label(correlated_trace_count, 'trace', 'traces')} "
            "show failed call chains from "
            f"{', '.join(upstream_services)} reaching this service."
        )

    return summary


def build_recommended_actions(top_root_cause: Dict) -> List[str]:
    service_name = top_root_cause.get("service_name")
    evidence = top_root_cause.get("evidence", {})

    actions = [
        f"Inspect recent logs for {service_name}.",
        f"Review failed traces involving {service_name}.",
    ]

    if evidence.get("high_latency_metric_count", 0) > 0:
        actions.append(
            f"Check latency sources for {service_name}, including downstream calls."
        )

    if evidence.get("error_log_count", 0) > 0:
        actions.append(
            f"Investigate ERROR log messages from {service_name}."
        )

    if evidence.get("failed_trace_count", 0) > 0:
        actions.append(
            f"Trace failed request paths where {service_name} appears."
        )

    return actions


def explain_rca(
    minutes: int | None = None,
    trace_id: str | None = None,
) -> Dict:
    rca_result = analyze_root_causes(minutes=minutes, trace_id=trace_id)
    top_root_causes = rca_result.get("top_root_causes", [])

    if not top_root_causes:
        return {
            "message": "No root cause candidates found",
            "time_window_minutes": minutes,
            "trace_id": trace_id,
            "explanation": (
                "No root cause explanation could be generated because "
                "there were no RCA candidates in the selected scope."
            ),
            "rca_result": rca_result,
        }

    top_root_cause = top_root_causes[0]

    summary = build_summary(top_root_cause)
    evidence_summary = build_evidence_summary(top_root_cause, trace_id)
    explanation = " ".join((summary.strip(), evidence_summary.strip()))

    return {
        "message": "RCA explanation generated",
        "time_window_minutes": minutes,
        "trace_id": trace_id,
        "root_cause_service": top_root_cause.get("service_name"),
        "confidence": top_root_cause.get("confidence"),
        "explanation": explanation,
        "key_reasons": format_reasons(top_root_cause.get("reasons", [])),
        "recommended_actions": build_recommended_actions(top_root_cause),
        "rca_result": rca_result,
    }