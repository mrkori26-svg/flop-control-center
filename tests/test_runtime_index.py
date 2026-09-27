import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from core.runtime_loop import read_runtime_index

NOW=datetime(2026,9,26,19,30,tzinfo=timezone.utc)

class RuntimeIndexTests(unittest.TestCase):
    def write_index(self, generated_at="2026-09-26T19:00:00Z", targets=True):
        root=Path(tempfile.mkdtemp()); path=root/"runtime-index.json"
        items=[{
            "targetId":"external-task-relay-paper","testCaseId":"case","updatedAt":generated_at,
            "currentStatus":"PASS","trustLevel":"EXTERNAL_RUNTIME","claimBoundary":"BOUND",
            "overall":{"runs":2},"windows":[
                {"label":"24h","metrics":{"runs":2,"conformancePassRate":1,"operationalAvailability":1}},
                {"label":"7d","metrics":{"runs":2,"conformancePassRate":1,"operationalAvailability":1}},
                {"label":"30d","metrics":{"runs":2,"conformancePassRate":1,"operationalAvailability":1}}
            ],"incidents":[]
        }] if targets else []
        path.write_text(json.dumps({
            "schema":"flop.runtime-public-index/v1","generatedAt":generated_at,"targets":items
        }),encoding="utf-8")
        return path

    def test_reads_multi_target_windows(self):
        result=read_runtime_index(self.write_index(),now=NOW)
        self.assertEqual(result["state"],"healthy")
        self.assertEqual(result["freshness"]["state"],"fresh")
        self.assertEqual(result["targets"][0]["trust_level"],"EXTERNAL_RUNTIME")
        self.assertEqual(result["targets"][0]["windows"]["30d"]["runs"],2)

    def test_empty_index_is_no_data(self):
        result=read_runtime_index(self.write_index(targets=False),now=NOW)
        self.assertEqual(result["state"],"no_data")

    def test_old_index_is_stale(self):
        result=read_runtime_index(self.write_index("2026-09-26T12:00:00Z"),now=NOW)
        self.assertEqual(result["state"],"stale")
        self.assertEqual(result["targets"][0]["freshness"]["state"],"stale")

if __name__=="__main__":
    unittest.main()
