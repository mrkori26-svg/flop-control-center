from __future__ import annotations

from typing import Any

SCHEMA = "flop.adopter-report.v1"
MODES = {"demo", "public-safe-local", "embedded-integrated"}
CLASSIFICATIONS = {"SELF_TEST", "EXTERNAL_REPORTED", "EXTERNAL_VERIFIED"}


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {"schema", "project", "platform", "mode", "classification", "evidence"}
    missing = sorted(required - set(report))
    if missing:
        errors.append("missing:" + ",".join(missing))
    if report.get("schema") != SCHEMA:
        errors.append("invalid_schema")
    if report.get("mode") not in MODES:
        errors.append("invalid_mode")
    if report.get("classification") not in CLASSIFICATIONS:
        errors.append("invalid_classification")
    for field in ("project", "platform"):
        if not isinstance(report.get(field), str) or not report.get(field, "").strip():
            errors.append(f"invalid_{field}")
    evidence = report.get("evidence")
    if not isinstance(evidence, list) or not evidence or not all(isinstance(x, str) and x.strip() for x in evidence):
        errors.append("invalid_evidence")
    return errors


PROFILES = [
    {'name': 'technocore-agent', 'use': 'Verify DID, mailbox and signed Technocore evidence.'},
    {'name': 'tclk-transcript', 'use': 'Verify signed TCLK transcript boundaries without claiming settlement.'},
    {'name': 'direct-rail-f1', 'use': 'Verify Appendix F.1 task_hash/report_data bytes and legacy rejection.'},
]


def adoption_entrypoint(external_reuse: dict[str, Any] | None = None) -> dict[str, Any]:
    reuse = (external_reuse or {}).get('counts', {})
    dependency = int(reuse.get('DEPENDENCY', 0)) + int(reuse.get('DURABLE_DEPENDENCY', 0))
    integrated = dependency + int(reuse.get('TOOL_REUSE', 0))
    return {
        'schema': 'flop.adoption-entrypoint.v1',
        'goal': 'first independent pinned CI consumer',
        'verified_external_ci': dependency,
        'integrated': integrated,
        'external_reuse': external_reuse or {'state': 'missing', 'counts': {}},
        'profiles': PROFILES,
        'quickstart': 'https://github.com/retardio73-boop/flop-conformance-lab/blob/main/docs/INTEGRATE_60_SECONDS.md',
        'matrix': 'https://github.com/retardio73-boop/flop-conformance-lab/blob/main/adoption/MATRIX.md',
        'rule': 'Only immutable external consumption plus reproducible external evidence counts as verified adoption.',
    }