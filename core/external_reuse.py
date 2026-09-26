import json
from pathlib import Path

STAGES = ("REPRODUCTION", "EVIDENCE_REUSE", "TOOL_REUSE", "DEPENDENCY", "DURABLE_DEPENDENCY")


def read_external_reuse(path):
    result = {"state": "missing", "total": 0, "counts": {stage: 0 for stage in STAGES}, "records": []}
    if not path:
        return result
    file = Path(path)
    if not file.exists():
        return result
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
        records = data.get("records", [])
        for record in records:
            stage = record.get("stage")
            if stage in result["counts"] and record.get("external") is True:
                result["counts"][stage] += 1
                result["records"].append(record)
        result["total"] = len(result["records"])
        result["state"] = "observed"
        return result
    except Exception as exc:
        return {**result, "state": "invalid", "error": str(exc)}
