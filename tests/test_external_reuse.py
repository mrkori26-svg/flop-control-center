import json
import tempfile
import unittest
from pathlib import Path
from core.external_reuse import read_external_reuse


class ExternalReuseTests(unittest.TestCase):
    def test_counts_only_explicit_external_records(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "reuse.json"
            path.write_text(json.dumps({"records": [
                {"stage": "EVIDENCE_REUSE", "external": True},
                {"stage": "DEPENDENCY", "external": True},
                {"stage": "DEPENDENCY", "external": False},
            ]}), encoding="utf-8")
            result = read_external_reuse(path)
            self.assertEqual(result["state"], "observed")
            self.assertEqual(result["total"], 2)
            self.assertEqual(result["counts"]["EVIDENCE_REUSE"], 1)
            self.assertEqual(result["counts"]["DEPENDENCY"], 1)


if __name__ == "__main__":
    unittest.main()
