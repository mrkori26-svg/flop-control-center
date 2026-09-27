from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA = "flop.adopter-report.v1"
REGISTRY_SCHEMA = "flop-conformance-adoption-registry/v1"
MODES = {"demo", "public-safe-local", "embedded-integrated"}
CLASSIFICATIONS = {"SELF_TEST", "EXTERNAL_REPORTED", "EXTERNAL_VERIFIED"}
REGISTRY_STATUSES = {"CANDIDATE", "PROPOSED", "INTEGRATED", "VERIFIED_EXTERNAL_CI"}


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


def read_adoption_registry(path: str | None) -> dict[str, Any]:
    result = {
        "schema": REGISTRY_SCHEMA,
        "state": "missing",
        "updated_at": None,
        "counts": {status: 0 for status in REGISTRY_STATUSES},
        "entries": [],
    }
    if not path:
        return result
    file = Path(path)
    if not file.exists():
        return {**result, "path": str(file)}
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except Exception as exc:
        return {**result, "state": "invalid", "path": str(file), "error": str(exc)}
    if data.get("schema") != REGISTRY_SCHEMA:
        return {**result, "state": "invalid", "path": str(file), "error": "unsupported_schema"}
    entries = data.get("entries")
    if not isinstance(entries, list):
        return {**result, "state": "invalid", "path": str(file), "error": "invalid_entries"}

    counts = {status: 0 for status in REGISTRY_STATUSES}
    accepted: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            return {**result, "state": "invalid", "path": str(file), "error": "invalid_entry"}
        implementation = entry.get("implementation")
        profile = entry.get("profile")
        status = entry.get("status")
        evidence = entry.get("evidence")
        if (
            not isinstance(implementation, str) or not implementation.strip()
            or not isinstance(profile, str) or not profile.strip()
            or status not in REGISTRY_STATUSES
            or not isinstance(evidence, dict)
        ):
            return {**result, "state": "invalid", "path": str(file), "error": "invalid_entry"}
        counts[status] += 1
        accepted.append(entry)

    return {
        **result,
        "state": "observed",
        "updated_at": data.get("updatedAt"),
        "counts": counts,
        "entries": accepted,
        "path": str(file),
    }


PROFILES = [
    {'name': 'technocore-agent', 'use': 'Verify DID, mailbox and signed Technocore evidence.'},
    {'name': 'tclk-transcript', 'use': 'Verify signed TCLK transcript boundaries without claiming settlement.'},
    {'name': 'direct-rail-f1', 'use': 'Verify Appendix F.1 task_hash/report_data bytes and legacy rejection.'},
]


def adoption_entrypoint(
    external_reuse: dict[str, Any] | None = None,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = registry or {
        "state": "missing",
        "counts": {status: 0 for status in REGISTRY_STATUSES},
        "entries": [],
    }
    counts = registry.get("counts", {})
    verified_external_ci = int(counts.get("VERIFIED_EXTERNAL_CI", 0))
    integrated = int(counts.get("INTEGRATED", 0)) + verified_external_ci
    return {
        'schema': 'flop.adoption-entrypoint.v1',
        'goal': 'first independent pinned CI consumer',
        'verified_external_ci': verified_external_ci,
        'integrated': integrated,
        'registry': registry,
        'external_reuse': external_reuse or {'state': 'missing', 'counts': {}},
        'profiles': PROFILES,
        'quickstart': 'https://github.com/retardio73-boop/flop-conformance-lab/blob/main/docs/INTEGRATE_60_SECONDS.md',
        'matrix': 'https://github.com/retardio73-boop/flop-conformance-lab/blob/main/adoption/MATRIX.md',
        'rule': 'Only registry status INTEGRATED or VERIFIED_EXTERNAL_CI counts as adoption; reuse is reported separately.',
    }
