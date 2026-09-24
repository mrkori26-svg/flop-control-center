import json
from core.empires_journeys import read_journeys

def test_reads_verified_empires_journey(tmp_path):
    path = tmp_path / "j1.json"
    path.write_text(json.dumps({
        "schema":"flop-empires-journey-evidence/v1",
        "journey_id":"empires_1",
        "capability":"empire.recon",
        "actor_did":"did:key:test",
        "request_id":"req-1",
        "transition":{"event_seq":4},
        "verification":{
            "native_signature":True,
            "router_request_binding":True,
            "runtime_binding":True,
            "replay":True,
        },
        "semantic_digest":"abc",
    }), encoding="utf-8")
    out = read_journeys(tmp_path)
    assert out["state"] == "observed"
    assert out["journeys"][0]["verified"] is True
    assert out["journeys"][0]["event_seq"] == 4
