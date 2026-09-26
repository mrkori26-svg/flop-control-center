def build_stack_overview(runtime, evidence, interactions, drift, external_reuse):
    runtime_state = runtime.get("state", "missing")
    evidence_count = len(evidence.get("records", []))
    interaction_state = interactions.get("check_status", "UNCHECKED")
    handoffs = drift.get("handoffs", [])
    reuse = external_reuse.get("counts", {})

    return {
        "schema": "flop.stack-overview.v1",
        "layers": [
            {"id": "ROUTE", "status": "OBSERVED", "detail": "Session Router repository and integration boundaries tracked."},
            {"id": "RUN", "status": "HEALTHY" if runtime_state == "observed" else "ATTENTION", "detail": f"Runtime observatory state: {runtime_state}."},
            {"id": "PROVE", "status": "HEALTHY" if evidence_count > 0 else "ATTENTION", "detail": f"{evidence_count} accepted evidence records."},
            {"id": "OBSERVE", "status": "HEALTHY" if interaction_state == "CHECKED" else "ATTENTION", "detail": f"Interactions {interaction_state}; {len(handoffs)} drift handoffs."},
        ],
        "external": {
            "reproduction": reuse.get("REPRODUCTION", 0),
            "evidence_reuse": reuse.get("EVIDENCE_REUSE", 0),
            "tool_reuse": reuse.get("TOOL_REUSE", 0),
            "dependency": reuse.get("DEPENDENCY", 0),
            "durable_dependency": reuse.get("DURABLE_DEPENDENCY", 0),
        },
    }
