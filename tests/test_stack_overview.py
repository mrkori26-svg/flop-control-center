import unittest
from core.stack_overview import build_stack_overview


class StackOverviewTests(unittest.TestCase):
    def test_layers_and_external_ladder_are_explicit(self):
        result = build_stack_overview(
            {"state": "observed"},
            {"records": [{"id": "e1"}]},
            {"check_status": "CHECKED"},
            {"handoffs": [{"id": "d1"}]},
            {"counts": {"EVIDENCE_REUSE": 2, "DEPENDENCY": 1}},
        )
        self.assertEqual([x["id"] for x in result["layers"]], ["ROUTE", "RUN", "PROVE", "OBSERVE"])
        self.assertTrue(all(x["status"] in {"OBSERVED", "HEALTHY", "ATTENTION"} for x in result["layers"]))
        self.assertEqual(result["external"]["evidence_reuse"], 2)
        self.assertEqual(result["external"]["dependency"], 1)


if __name__ == "__main__":
    unittest.main()
