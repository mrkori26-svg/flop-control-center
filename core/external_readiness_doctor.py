"""Read-only, evidence-gated readiness doctor for FLOP agent operation.

Never interprets locally reported PASS, TCLK messages, an HTTP response, or
Passport telemetry as finalized-chain inference settlement.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _read(path: Path) -> dict:
    try:
        if path.stat().st_size > 5 * 1024 * 1024:
            return {}
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
        return obj if isinstance(obj, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def _age(stamp: object, now: datetime, limit: int) -> dict:
    if not isinstance(stamp, str) or not stamp:
        return {"state": "UNKNOWN", "ageSeconds": None, "sourceAt": stamp}
    try:
        dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("timezone required")
        age = (now - dt.astimezone(timezone.utc)).total_seconds()
    except (TypeError, ValueError, OverflowError):
        return {"state": "INVALID", "ageSeconds": None, "sourceAt": stamp}
    return {"state": "FRESH" if -60 <= age <= limit else "STALE",
            "ageSeconds": round(age, 1), "sourceAt": stamp}


def snapshot(root: Path, *, now: datetime | None = None, local_appdata: Path | None = None) -> dict:
    """Inspect local observation and external evidence boundaries without side effects."""
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    app = Path(local_appdata) if local_appdata is not None else Path(
        os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    )
    worker = root / "useful-work-operator"
    eco = _read(worker / "ecosystem" / "ecosystem-status.json")
    operator = _read(worker / "state" / "operator-supervisor-heartbeat.json")
    ecosystem = _read(worker / "ecosystem" / "ecosystem-supervisor-heartbeat.json")
    kibble = _read(worker / "state" / "kibble-compliance.json")
    qual = _read(worker / "ecosystem" / "harness" / "state" / "qualification.json")
    block = _read(worker / "state-blockrewards-0-of-1" / "status.json")
    signer = _read(app / "Technocore" / "signer-health.json")
    probe = _read(app / "Technocore" / "probe-agent" / "runtime-heartbeat.json")
    adoption = _read(root / "flop-conformance-lab" / "adoption" / "registry.json")
    buyer = _read(root / "flop-session-router" / "examples" / "flop-buyer.disabled.json")
    testnet = _read(root / "flop-session-router" / "examples" / "flop-public-testnet.disabled.json")

    operator_fresh = _age(operator.get("at"), now, 180)
    ecosystem_fresh = _age(ecosystem.get("at"), now, 180)
    signer_fresh = _age(signer.get("checkedAt"), now, 420)
    kibble_fresh = _age(kibble.get("checkedAt"), now, 300)
    qual_fresh = _age(qual.get("generatedAt"), now, 600)
    market = eco.get("market") if isinstance(eco.get("market"), dict) else {}
    market_fresh = _age(market.get("asOf"), now, 600)
    probe_ms = probe.get("attemptAt")
    probe_stamp = None
    if isinstance(probe_ms, (int, float)):
        try:
            probe_stamp = datetime.fromtimestamp(probe_ms / 1000, timezone.utc).isoformat()
        except (ValueError, OverflowError, OSError):
            pass
    probe_fresh = _age(probe_stamp, now, 120)
    lanes = operator.get("lanes") if isinstance(operator.get("lanes"), list) else []
    expected = {"general", "blockrewards-0-of-1", "harness-0-of-1"}
    active = {entry.get("id") for entry in lanes if isinstance(entry, dict) and isinstance(entry.get("pid"), int)}
    healthy_operator = operator.get("healthy") is True and operator_fresh["state"] == "FRESH" and expected.issubset(active)
    healthy_ecosystem = ecosystem.get("healthy") is True and ecosystem_fresh["state"] == "FRESH"
    healthy_signer = signer.get("ok") is True and signer.get("status") == "HEALTHY" and signer.get("privateMaterialExported") is False and signer_fresh["state"] == "FRESH"
    healthy_probe = probe.get("status") == "OK" and probe.get("runtimeStatus") == "ACTIVE" and probe.get("consecutiveFailures") == 0 and probe_fresh["state"] == "FRESH"
    freshness = {
        "operator": operator_fresh,
        "ecosystem": ecosystem_fresh,
        "signer": signer_fresh,
        "probe": probe_fresh,
        "kibble": kibble_fresh,
        "passport": qual_fresh,
        "market": market_fresh,
    }
    blockers = []
    def block_on(code: str, scope: str, detail: str) -> None:
        blockers.append({"code": code, "scope": scope, "detail": detail})
    if not healthy_operator:
        block_on("OPERATOR_NOT_HEALTHY", "local", "Three canonical worker lanes require fresh, healthy supervision.")
    if not healthy_ecosystem:
        block_on("ECOSYSTEM_NOT_HEALTHY", "local", "Ecosystem supervisor evidence is absent or stale.")
    if not healthy_signer:
        block_on("SIGNER_NOT_HEALTHY", "local", "CurrentUser signer health must be verified without exporting keys.")
    if not healthy_probe:
        block_on("PROBE_NOT_ACTIVE", "local", "Technocore Probe requires a fresh successful runtime heartbeat.")
    if market_fresh["state"] != "FRESH" or market.get("fresh") is not True:
        block_on("MARKET_SOURCE_STALE", "external", "Fresh scanner output does not repair stale upstream market timestamps.")
    if kibble.get("externalAuthorityState") != "AVAILABLE" or kibble_fresh["state"] != "FRESH":
        block_on("KIBBLE_AUTHORITY_UNVERIFIED", "external", "Kibble scoreboard/payer authority is not currently verified.")
    published = qual.get("published") if isinstance(qual.get("published"), dict) else {}
    passport_valid = (qual_fresh["state"] == "FRESH" and published.get("passportPresent") is True
                      and published.get("upstreamFresh") is True and published.get("provisional") is False)
    if not passport_valid:
        block_on("PASSPORT_NOT_CURRENTLY_PUBLISHED", "external", "Historical TCLK payer reviews are not current Passport publication.")
    # Configs are intentionally disabled examples; no implicit permission to spend.
    if buyer.get("enabled") is not False or testnet.get("purchaseEnabled") is not False:
        block_on("BUYER_CONFIGURATION_UNVERIFIED", "testnet", "Production buyer configuration must be reviewed before deployment.")
    else:
        block_on("BUYER_PURCHASE_DISABLED", "testnet", "Only LOCAL_TEST transport is available; economic execution remains disabled.")
    block_on("OFFICIAL_TESTNET_ACCESS_UNVERIFIED", "testnet", "No independently pinned official account admission and finalized chain transport.")
    block_on("DID_CHAIN_ACCOUNT_BINDING_UNVERIFIED", "testnet", "A Technocore DID is not proof of a chain account or authority.")
    block_on("FLOP_RUNTIME_AND_CUSTODY_UNVERIFIED", "testnet", "Official runtime metadata, signed quote and restricted transaction signing are required.")
    block_on("FINALIZED_INFERENCE_SETTLEMENT_UNVERIFIED", "testnet", "Only independently verified finalized proof, fee and account delta count.")

    tracker = block.get("passTracker") if isinstance(block.get("passTracker"), dict) else {}
    live = qual.get("effective") if isinstance(qual.get("effective"), dict) else {}
    return {
        "schema": "flop.external-readiness-doctor/v1",
        "generatedAt": now.isoformat(),
        "readOnly": True,
        "localStatus": "HEALTHY" if all((healthy_operator, healthy_ecosystem, healthy_signer, healthy_probe)) else "DEGRADED",
        "externalStatus": "BLOCKED_BY_UPSTREAM" if any(x["scope"] == "external" for x in blockers) else "UNVERIFIED",
        "testnetStatus": "BLOCKED_UNVERIFIED",
        "freshness": freshness,
        "services": {"operator": healthy_operator, "ecosystem": healthy_ecosystem,
                     "signer": healthy_signer, "probe": healthy_probe},
        "work": {
            "blockrewards": {
                "locallyObservedPayerPass": int(live.get("passes") or 0),
                "locallyObservedPayerFail": int(live.get("fails") or 0),
                "trackerReportedExternalSuccess": int(tracker.get("externalSuccess") or 0),
                "verifiedFullExternalCycles": None,
                "verificationState": "UNVERIFIED_FROM_AVAILABLE_EVIDENCE",
                "claim": "Only funded -> claimed -> delivered -> reviewed -> receipt discoverable -> passport indexed counts."
            },
            "kibble": {"authority": kibble.get("externalAuthorityState", "UNKNOWN"),
                       "scoreError": str(kibble.get("scoreError") or "")[:80],
                       "counts": {k: int((kibble.get("counts") or {}).get(k) or 0) for k in
                                  ("externalObservedUseful", "externalObservedRejected", "unknownOutsideRetention")}},
            "passport": {"publishedPass": int(published.get("passes") or 0), "upstreamFresh": bool(published.get("upstreamFresh")),
                         "passportPresent": bool(published.get("passportPresent"))},
        },
        "adoption": {"registryStatus": str(adoption.get("state") or "UNKNOWN"),
                     "independentVerified": 0,
                     "claim": "Candidate/PROPOSED registry entries do not certify independent adoption."},
        "blockers": blockers,
        "claimBoundary": "No local PASS, TCLK transcript, HTTP reply, self-signed receipt or dashboard counter is official FLOP chain settlement.",
    }
