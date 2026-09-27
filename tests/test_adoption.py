import json
import tempfile
import unittest
from pathlib import Path

from core.adoption import adoption_entrypoint, read_adoption_registry, validate_report


def valid_report(classification="EXTERNAL_REPORTED"):
    return {
        "schema": "flop.adopter-report.v1",
        "project": "example/project",
        "repository": "https://github.com/example/project",
        "platform": "Ubuntu 24.04",
        "mode": "public-safe-local",
        "classification": classification,
        "control_center_ref": "main",
        "evidence": ["https://github.com/example/project/actions/runs/1"],
        "notes": None,
    }


def write_registry(entries):
    root=Path(tempfile.mkdtemp())
    path=root/"registry.json"
    path.write_text(json.dumps({
        "schema":"flop-conformance-adoption-registry/v1",
        "updatedAt":"2026-09-27T00:00:00Z",
        "entries":entries,
    }),encoding="utf-8")
    return path


class AdoptionTests(unittest.TestCase):
    def test_valid_external_report(self):
        self.assertEqual(validate_report(valid_report()), [])

    def test_self_test_is_explicit_not_external_verified(self):
        report = valid_report("SELF_TEST")
        self.assertEqual(validate_report(report), [])
        self.assertNotEqual(report["classification"], "EXTERNAL_VERIFIED")

    def test_report_requires_evidence_and_known_schema(self):
        report = valid_report()
        report["evidence"] = []
        report["schema"] = "unknown"
        errors = validate_report(report)
        self.assertIn("invalid_evidence", errors)
        self.assertIn("invalid_schema", errors)

    def test_proposed_entries_do_not_count_as_adoption(self):
        registry=read_adoption_registry(write_registry([{
            "implementation":"example/project","profile":"tclk-transcript","status":"PROPOSED","evidence":{"pullRequest":"https://example/pr/1"}
        }]))
        result=adoption_entrypoint({"state":"observed","counts":{"DEPENDENCY":4,"DURABLE_DEPENDENCY":2}},registry)
        self.assertEqual(result["integrated"],0)
        self.assertEqual(result["verified_external_ci"],0)

    def test_registry_is_sole_source_for_integrated_and_verified_ci_counts(self):
        registry=read_adoption_registry(write_registry([
            {"implementation":"a/project","profile":"tclk-transcript","status":"INTEGRATED","evidence":{"commit":"a"*40}},
            {"implementation":"b/project","profile":"direct-rail-f1","status":"VERIFIED_EXTERNAL_CI","evidence":{"run":"https://example/actions/1"}},
            {"implementation":"c/project","profile":"technocore-agent","status":"CANDIDATE","evidence":{"reason":"candidate"}},
        ]))
        result=adoption_entrypoint({"state":"observed","counts":{"DEPENDENCY":99}},registry)
        self.assertEqual(result["integrated"],2)
        self.assertEqual(result["verified_external_ci"],1)
        self.assertEqual(result["registry"]["counts"]["CANDIDATE"],1)

    def test_invalid_registry_fails_closed_to_zero_adoption(self):
        path=write_registry([])
        data=json.loads(path.read_text(encoding="utf-8"))
        data["schema"]="unknown"
        path.write_text(json.dumps(data),encoding="utf-8")
        registry=read_adoption_registry(path)
        self.assertEqual(registry["state"],"invalid")
        result=adoption_entrypoint(None,registry)
        self.assertEqual(result["integrated"],0)
        self.assertEqual(result["verified_external_ci"],0)


if __name__ == '__main__':
    unittest.main()
