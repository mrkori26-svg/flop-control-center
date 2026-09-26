import json
import tempfile
import unittest
from pathlib import Path
from core.runtime_loop import read_runtime_index

class RuntimeIndexTests(unittest.TestCase):
    def test_reads_multi_target_windows(self):
        root=Path(tempfile.mkdtemp()); path=root/"runtime-index.json"
        path.write_text(json.dumps({
            "schema":"flop.runtime-public-index/v1","generatedAt":"2026-09-26T19:00:00Z",
            "targets":[{
                "targetId":"external-task-relay-paper","testCaseId":"case","updatedAt":"2026-09-26T19:00:00Z",
                "currentStatus":"PASS","trustLevel":"EXTERNAL_RUNTIME","claimBoundary":"BOUND",
                "overall":{"runs":2},"windows":[
                    {"label":"24h","metrics":{"runs":2,"conformancePassRate":1,"operationalAvailability":1}},
                    {"label":"7d","metrics":{"runs":2,"conformancePassRate":1,"operationalAvailability":1}},
                    {"label":"30d","metrics":{"runs":2,"conformancePassRate":1,"operationalAvailability":1}}
                ],"incidents":[]
            }]
        }),encoding="utf-8")
        result=read_runtime_index(path)
        self.assertEqual(result["state"],"healthy")
        self.assertEqual(result["targets"][0]["trust_level"],"EXTERNAL_RUNTIME")
        self.assertEqual(result["targets"][0]["windows"]["30d"]["runs"],2)

if __name__=="__main__":
    unittest.main()
