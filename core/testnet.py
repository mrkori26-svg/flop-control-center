import json
from pathlib import Path


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def snapshot(root: Path):
    runtime = root / "flop-conformance-lab" / ".runtime"
    latest = _read_json(runtime / "flop-testnet-latest.json")
    if not latest:
        return {
            "schema": "flop.control-center-testnet/v1",
            "state": "NOT_AVAILABLE",
            "live_verified": False,
            "claim_boundary": "NO_OFFICIAL_TESTNET_EVIDENCE",
            "metrics": {
                "settled_sessions": 0,
                "verified_compute": 0,
                "flop_spent": 0,
                "distinct_miners": 0,
                "valid_proofs": 0,
            },
        }

    fingerprint = latest.get("target", {}).get("fingerprint", {})
    readiness = fingerprint.get("readiness", "NOT_AVAILABLE")
    execution = latest.get("execution", {})
    evidence = latest.get("evidence", {})
    sessions = evidence.get("sessions", []) if isinstance(evidence, dict) else []
    miners = {
        str(item.get("miner"))
        for item in sessions
        if isinstance(item, dict) and item.get("miner")
    }
    return {
        "schema": "flop.control-center-testnet/v1",
        "state": readiness,
        "live_verified": readiness == "LIVE_VERIFIED",
        "claim_boundary": "OFFICIAL_NETWORK_SESSION_ONLY",
        "network": fingerprint.get("network"),
        "genesis_hash": fingerprint.get("genesisHash"),
        "chain_id": fingerprint.get("chainId"),
        "observed_at": latest.get("observedAt"),
        "verification": latest.get("verification", {}),
        "metrics": {
            "settled_sessions": sum(
                1 for item in sessions
                if isinstance(item, dict) and item.get("settled") is True
            ),
            "verified_compute": sum(
                float(item.get("verified_compute", 0) or 0)
                for item in sessions if isinstance(item, dict)
            ),
            "flop_spent": sum(
                float(item.get("flop_spent", 0) or 0)
                for item in sessions if isinstance(item, dict)
            ),
            "distinct_miners": len(miners),
            "valid_proofs": sum(
                1 for item in sessions
                if isinstance(item, dict) and item.get("proof_valid") is True
            ),
        },
        "execution_present": bool(execution),
        "read_only": True,
    }
