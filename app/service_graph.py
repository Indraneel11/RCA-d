"""Find failed service calls within distributed traces."""

from collections import defaultdict
from typing import Dict, List


# Each key is a caller; its values are services it calls.
SERVICE_DEPENDENCIES = {
    "frontend-service": ("order-service",),
    "order-service": ("payment-service",),
    "payment-service": (),
}

POINTS_PER_CORRELATED_CALLER = 2
MAX_GRAPH_BONUS = 6


def correlate_failed_calls(traces: List[Dict]) -> Dict[str, Dict]:
    """Find failed dependencies whose callers also failed in the same trace."""

    # Group spans by trace_id, then by span_id. This lets us find a span's parent.
    by_trace = defaultdict(dict)

    for span in traces:
        trace_id = span.get("trace_id")
        span_id = span.get("span_id")

        if trace_id and span_id:
            by_trace[trace_id][span_id] = span

    matched_callers = defaultdict(set)
    correlated_traces = defaultdict(set)

    for trace_id, spans in by_trace.items():
        for span in spans.values():
            service = span.get("service_name")

            if span.get("status") != "error" or not service:
                continue

            child = span
            visited = {span.get("span_id")}

            # Walk upward through this span's parent chain.
            while child.get("parent_span_id"):
                parent_id = child["parent_span_id"]

                if parent_id in visited:
                    break

                visited.add(parent_id)
                parent = spans.get(parent_id)

                if not parent or parent.get("status") != "error":
                    break

                caller = parent.get("service_name")
                dependency = child.get("service_name")

                # Verify that this observed call matches our service graph.
                if dependency not in SERVICE_DEPENDENCIES.get(caller, ()):
                    break

                # Count a caller only once per trace for this candidate.
                matched_callers[service].add((trace_id, caller))
                correlated_traces[service].add(trace_id)

                child = parent

    return {
        service: {
            "graph_bonus": min(
                MAX_GRAPH_BONUS,
                len(callers) * POINTS_PER_CORRELATED_CALLER,
            ),
            "upstream_failed_services": sorted(
                {caller for _, caller in callers}
            ),
            "correlated_trace_count": len(correlated_traces[service]),
        }
        for service, callers in matched_callers.items()
    }