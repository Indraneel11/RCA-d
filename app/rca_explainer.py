from typing import Dict, List

from app.rca_engine import analyze_root_causes


def format_reasons(reasons: List[str]) -> List[str]:
    return reasons[:5]


def build_summary(top_root_cause: Dict) -> str:
    service_name = top_root_cause.get("service_name")
    confidence = top_root_cause.get("confidence")
    score = top_root_cause.get("score")

    return (
        f"The most likely root cause is {service_name}. "
        f"The RCA engine assigned it {confidence} confidence "
        f"with a score of {score}."
    )


def build_evidence_summary(top_root_cause: Dict) -> str:
    evidence = top_root_cause.get("evidence", {})

    incident_count = evidence.get("incident_count", 0)
    error_log_count = evidence.get("error_log_count", 0)
    failed_trace_count = evidence.get("failed_trace_count", 0)
    high_latency_metric_count = evidence.get("high_latency_metric_count", 0)
    correlated_trace_count = evidence.get("correlated_trace_count", 0)
    upstream_services = evidence.get("upstream_failed_services", [])

    summary = (
        f"Evidence includes {incident_count} related incidents, "
        f"{error_log_count} ERROR logs, "
        f"{failed_trace_count} failed trace spans, and "
        f"{high_latency_metric_count} high-latency metrics."
    )

    if correlated_trace_count:
        summary += (
            f" {correlated_trace_count} trace(s) also show failed calls from "
            f"{', '.join(upstream_services)} to this dependency."
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


def explain_rca(minutes: int | None = None) -> Dict:
    rca_result = analyze_root_causes(minutes=minutes)
    top_root_causes = rca_result.get("top_root_causes", [])

    if not top_root_causes:
        return {
            "message": "No root cause candidates found",
            "time_window_minutes": minutes,
            "explanation": (
                "No root cause explanation could be generated because "
                "there were no RCA candidates in the selected time window."
            ),
            "rca_result": rca_result,
        }

    top_root_cause = top_root_causes[0]

    summary = build_summary(top_root_cause)
    evidence_summary = build_evidence_summary(top_root_cause)
    key_reasons = format_reasons(top_root_cause.get("reasons", []))
    recommended_actions = build_recommended_actions(top_root_cause)

    explanation = f"{summary} {evidence_summary}"

    return {
        "message": "RCA explanation generated",
        "time_window_minutes": minutes,
        "root_cause_service": top_root_cause.get("service_name"),
        "confidence": top_root_cause.get("confidence"),
        "explanation": explanation,
        "key_reasons": key_reasons,
        "recommended_actions": recommended_actions,
        "rca_result": rca_result,
    }