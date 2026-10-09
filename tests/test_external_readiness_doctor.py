import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from core.external_readiness_doctor import snapshot, _age


NOW = datetime(2026, 10, 9, 23, 20, tzinfo=timezone.utc)
AT = NOW.isoformat()


class ExternalReadinessDoctorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "stack"
        self.app = Path(self.tmp.name) / "app"

    def put(self, name, data, *, app=False):
        path = (self.app if app else self.root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def ready_local(self):
        w = "useful-work-operator/"
        self.put(w + "state/operator-supervisor-heartbeat.json",
                 {"at": AT, "healthy": True, "lanes": [
                     {"id": n, "pid": i+1} for i,n in enumerate(
                         ("general", "blockrewards-0-of-1", "harness-0-of-1"))]})
        self.put(w + "ecosystem/ecosystem-supervisor-heartbeat.json", {"at": AT, "healthy": True})
        self.put("Technocore/signer-health.json", {"checkedAt": AT, "status": "HEALTHY", "ok": True,
                 "privateMaterialExported": False}, app=True)
        self.put("Technocore/probe-agent/runtime-heartbeat.json", {"attemptAt": int(NOW.timestamp()*1000),
                 "runtimeStatus": "ACTIVE", "status": "OK", "consecutiveFailures": 0}, app=True)
        self.put(w + "ecosystem/ecosystem-status.json", {"generatedAt": AT, "market": {"fresh": True, "asOf": AT}})
        self.put(w + "state/kibble-compliance.json", {"checkedAt": AT, "externalAuthorityState": "AVAILABLE",
                 "counts": {"externalObservedUseful": 5}})
        self.put(w + "ecosystem/harness/state/qualification.json", {"generatedAt": AT,
                 "effective": {"passes": 36, "fails": 5},
                 "published": {"passes": 36, "passportPresent": True, "upstreamFresh": True, "provisional": False}})
        self.put(w + "state-blockrewards-0-of-1/status.json", {"passTracker": {"externalSuccess": 99}})
        self.put("flop-session-router/examples/flop-buyer.disabled.json", {"enabled": False})
        self.put("flop-session-router/examples/flop-public-testnet.disabled.json", {"purchaseEnabled": False})

    def doctor(self):
        return snapshot(self.root, now=NOW, local_appdata=self.app)

    def test_empty_sources_fail_closed_without_exceptions(self):
        doc = self.doctor()
        self.assertEqual(doc["localStatus"], "DEGRADED")
        self.assertEqual(doc["testnetStatus"], "BLOCKED_UNVERIFIED")
        self.assertIsNone(doc["work"]["blockrewards"]["verifiedFullExternalCycles"])
        self.assertIn("MARKET_SOURCE_STALE", [x["code"] for x in doc["blockers"]])

    def test_healthy_local_processes_do_not_certify_testnet_or_external_success(self):
        self.ready_local()
        doc = self.doctor()
        self.assertEqual(doc["localStatus"], "HEALTHY")
        self.assertEqual(doc["work"]["blockrewards"]["locallyObservedPayerPass"], 36)
        self.assertEqual(doc["work"]["blockrewards"]["trackerReportedExternalSuccess"], 99)
        self.assertIsNone(doc["work"]["blockrewards"]["verifiedFullExternalCycles"])
        self.assertEqual(doc["testnetStatus"], "BLOCKED_UNVERIFIED")
        self.assertEqual(doc["externalStatus"], "UNVERIFIED")

    def test_stale_market_is_not_hidden_by_fresh_scanner_generation(self):
        self.ready_local()
        self.put("useful-work-operator/ecosystem/ecosystem-status.json", {
            "generatedAt": AT, "market": {"fresh": False, "asOf": "2026-09-24T23:00:00Z"}})
        doc = self.doctor()
        self.assertEqual(doc["freshness"]["market"]["state"], "STALE")
        self.assertIn("MARKET_SOURCE_STALE", [x["code"] for x in doc["blockers"]])

    def test_bad_signer_and_future_clock_fail_closed(self):
        self.ready_local()
        self.put("Technocore/signer-health.json", {"checkedAt": AT, "status": "HEALTHY",
                 "ok": True, "privateMaterialExported": True}, app=True)
        self.assertEqual(self.doctor()["localStatus"], "DEGRADED")
        self.assertEqual(_age("2030-01-01T00:00:00Z", NOW, 180)["state"], "STALE")
        self.assertEqual(_age("invalid", NOW, 180)["state"], "INVALID")

    def test_sensitive_local_fields_are_not_echoed(self):
        self.ready_local()
        self.put("useful-work-operator/state-blockrewards-0-of-1/status.json", {
            "passTracker": {"externalSuccess": 0}, "token": "PRIVATE_SENTINEL", "secret": "PRIVATE_SENTINEL"})
        doc = self.doctor()
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(doc))


if __name__ == "__main__":
    unittest.main()
