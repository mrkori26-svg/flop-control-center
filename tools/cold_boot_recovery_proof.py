from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\Users\acost\flop stack")
LOCAL = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
OUT_DIR = LOCAL / "FLOP" / "recovery"
OUT = OUT_DIR / "cold-boot-proof.json"
PY312 = LOCAL / "Programs" / "Python" / "Python312" / "python.exe"
SIGNER_PY = ROOT / "technocore-did-starter" / ".venv" / "Scripts" / "python.exe"
SIGNER_CLIENT = ROOT / "technocore-did-starter" / "signer_client.py"
EXPORT = ROOT / "flop-control-center" / "tools" / "export_stack_state.py"
ROOT_AUDIT = ROOT / "useful-work-operator" / "ecosystem" / "root-audit.mjs"
STATE = ROOT / "FLOP_STACK_STATE.json"
PROBE_HEARTBEAT = LOCAL / "Technocore" / "probe-agent" / "runtime-heartbeat.json"
WORK_HEARTBEAT = ROOT / "useful-work-operator" / "state" / "operator-supervisor-heartbeat.json"
OBS_HEARTBEAT = ROOT / "flop-conformance-lab" / ".runtime" / "observatory-supervisor.json"

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(args, *, input_text: str | None = None, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(x) for x in args],
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def export_state_with_retry(attempts: int = 15, delay_seconds: float = 1.0) -> subprocess.CompletedProcess[str]:
    last = None
    for _ in range(attempts):
        last = run([PY312, EXPORT], timeout=60)
        combined = (last.stdout or "") + "\n" + (last.stderr or "")
        if last.returncode == 0:
            return last
        if "FLOP_STACK_STATE_WRITER_ALREADY_RUNNING" not in combined:
            return last
        time.sleep(delay_seconds)
    assert last is not None
    return last


def signer_status() -> dict:
    p = run(
        [SIGNER_PY, SIGNER_CLIENT],
        input_text=json.dumps({"operation": "status"}),
        timeout=15,
    )
    try:
        data = json.loads(p.stdout or "{}")
    except Exception:
        data = {}
    return {
        "returncode": p.returncode,
        "ok": bool(data.get("ok")),
        "signer_available": bool(data.get("signer_available")),
        "did": data.get("did"),
        "privateMaterialExported": bool(data.get("privateMaterialExported", False)),
        "error": data.get("error") or (p.stderr.strip()[:300] if p.stderr else None),
    }


def task(command: str, name: str) -> dict:
    p = run(["schtasks.exe", f"/{command}", "/TN", name], timeout=20)
    return {"task": name, "command": command, "returncode": p.returncode, "stdout": p.stdout.strip()[-500:], "stderr": p.stderr.strip()[-500:]}


def matching_pids(pattern: str) -> list[int]:
    # Enumerate actual interpreter processes; never match the PowerShell query
    # itself, other shells or the desktop remote-control host.
    p = run(["powershell.exe", "-NoProfile", "-Command",
             "@(Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('python.exe','pythonw.exe','node.exe') } | Select-Object ProcessId,CommandLine) | ConvertTo-Json -Compress"], timeout=20)
    if p.returncode != 0:
        raise RuntimeError("RECOVERY_PROCESS_ENUMERATION_FAILED")
    rows = json.loads(p.stdout or "[]")
    if isinstance(rows, dict):
        rows = [rows]
    return [int(row["ProcessId"]) for row in rows
            if row.get("CommandLine") and str(ROOT).lower() in row["CommandLine"].lower()
            and re.search(pattern, row["CommandLine"], re.IGNORECASE)
            and int(row["ProcessId"]) != os.getpid()]


def kill_matching(pattern: str) -> list[int]:
    pids = matching_pids(pattern)
    for pid in pids:
        p = run(["powershell.exe", "-NoProfile", "-Command",
                 f"Stop-Process -Id {pid} -Force -ErrorAction Stop"], timeout=20)
        if p.returncode != 0 and pid in matching_pids(pattern):
            # /END or an owner may have already exited this process after enumeration.
            # A surviving matching process is still a hard failure.
            raise RuntimeError(f"RECOVERY_PROCESS_STOP_FAILED:{pid}")
    return pids


def reconstructed_local_health(state: dict) -> bool:
    """Assess all other sources while the recovery proof itself is running.

    External blockers remain visible and cannot become settlement claims.
    Only the self-reference is excluded; missing or stale local evidence fails.
    """
    components = state.get("components")
    if state.get("freshness_status") != "fresh" or not isinstance(components, dict):
        return False
    required = {"operator", "ecosystem", "root_audit", "probe", "signer", "observatory"}
    if not required.issubset(components):
        return False
    return all(item.get("freshness_status") == "fresh"
               and item.get("state") in {"healthy", "blocked_external", "telemetry_stale"}
               for name, item in components.items() if name != "recovery_proof")


def fresh(path: Path, max_age: float) -> bool:
    try:
        return time.time() - path.stat().st_mtime <= max_age
    except OSError:
        return False


def wait_until(predicate, timeout: int, interval: float = 2.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return bool(predicate())


def execute_rehearsal() -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    started = now()
    baseline_state = read_json(STATE)
    baseline_signer = signer_status()
    baseline_probe = read_json(PROBE_HEARTBEAT)
    baseline_work = read_json(WORK_HEARTBEAT)
    baseline_obs = read_json(OBS_HEARTBEAT)
    baseline_obs_pids = set(matching_pids(r"observatory-supervisor\.py"))

    actions = []
    actions.append(task("RUN", "TechnocoreSignerWatchdog"))
    time.sleep(1)
    signer_after_watchdog = signer_status()

    actions.append(task("END", "TechnocoreProbeAgent"))
    actions.append(task("END", "FLOPUnifiedObservatory"))
    killed_probe = kill_matching(r"probe_agent_bootstrap\.py")
    killed_observatory = kill_matching(r"observatory-supervisor\.py")
    killed_work = kill_matching(r"operator-supervisor\.mjs")
    killed_work_lanes = kill_matching(r"[\\/]useful-work-operator[\\/]operator\.mjs")

    actions.append(task("RUN", "TechnocoreProbeAgent"))
    actions.append(task("RUN", "FLOPUnifiedObservatory"))
    actions.append(task("RUN", "FLOPUsefulWorkOperatorWatchdog"))

    probe_ok = wait_until(
        lambda: fresh(PROBE_HEARTBEAT, 90)
        and read_json(PROBE_HEARTBEAT).get("status") == "OK"
        and read_json(PROBE_HEARTBEAT).get("runtimeStatus") == "ACTIVE"
        and read_json(PROBE_HEARTBEAT).get("runtimeInstanceId") not in {None, baseline_probe.get("runtimeInstanceId")},
        90,
    )
    work_ok = wait_until(
        lambda: fresh(WORK_HEARTBEAT, 120)
        and read_json(WORK_HEARTBEAT).get("healthy") is True
        and read_json(WORK_HEARTBEAT).get("pid") not in {None, baseline_work.get("pid")},
        90,
    )
    obs_process_ok = wait_until(
        lambda: bool(set(matching_pids(r"observatory-supervisor\.py")) - baseline_obs_pids),
        30,
    )
    obs_health_ok = wait_until(
        lambda: fresh(OBS_HEARTBEAT, 300)
        and read_json(OBS_HEARTBEAT).get("status") == "HEALTHY"
        and str(read_json(OBS_HEARTBEAT).get("checkedAt") or "") > str(baseline_obs.get("checkedAt") or ""),
        600,
        interval=5.0,
    )

    # Break the self-reference deliberately: while validating the reconstructed stack,
    # publish an explicit RUNNING interim proof, which remains unverified. A stale/previous FAIL proof must not
    # make the recovery test fail merely because it is the component under test.
    interim = {
        "schema": "flop.cold-boot-recovery-proof/v1",
        "startedAt": started,
        "finishedAt": None,
        "status": "RUNNING",
        "checks": {
            "signer_available_without_key_export": bool(
                signer_after_watchdog.get("ok")
                and signer_after_watchdog.get("signer_available")
                and not signer_after_watchdog.get("privateMaterialExported")
            ),
            "probe_recovered": probe_ok,
            "work_engine_recovered": work_ok,
            "observatory_recovered": bool(obs_process_ok and obs_health_ok),
            "state_reconstructed_from_evidence": False,
            "stack_returned_healthy": False,
        },
        "claimBoundary": "Interim local recovery rehearsal state; not external availability or upstream recognition.",
    }
    OUT.write_text(json.dumps(interim, indent=2) + "\n", encoding="utf-8")

    root_audit = run(["node.exe", ROOT_AUDIT], timeout=120)
    export = export_state_with_retry()
    final_state = read_json(STATE)
    final_signer = signer_status()

    checks = {
        "signer_available_without_key_export": bool(
            final_signer.get("ok")
            and final_signer.get("signer_available")
            and not final_signer.get("privateMaterialExported")
        ),
        "probe_recovered": probe_ok,
        "work_engine_recovered": work_ok,
        "observatory_recovered": bool(obs_process_ok and obs_health_ok),
        "state_reconstructed_from_evidence": root_audit.returncode == 0 and export.returncode == 0 and final_state.get("freshness_status") == "fresh",
        "stack_returned_healthy": reconstructed_local_health(final_state),
    }
    proof = {
        "schema": "flop.cold-boot-recovery-proof/v1",
        "startedAt": started,
        "finishedAt": now(),
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "baseline": {
            "stackState": baseline_state.get("state"),
            "externalState": baseline_state.get("external_state"),
            "signer": baseline_signer,
            "probeRuntimeInstanceId": baseline_probe.get("runtimeInstanceId"),
            "workSupervisorPid": baseline_work.get("pid"),
            "observatoryCheckedAt": baseline_obs.get("checkedAt"),
        },
        "recovery": {
            "actions": actions,
            "killedProbePids": killed_probe,
            "killedObservatoryPids": killed_observatory,
            "killedWorkSupervisorPids": killed_work,
            "killedWorkLanePids": killed_work_lanes,
            "signerAfterWatchdog": signer_after_watchdog,
        },
        "final": {
            "stackState": final_state.get("state"),
            "externalState": final_state.get("external_state"),
            "freshness": final_state.get("freshness_status"),
            "signer": final_signer,
            "exportReturnCode": export.returncode,
            "exportStdout": export.stdout.strip()[-1000:],
            "exportStderr": export.stderr.strip()[-1000:],
        },
        "claimBoundary": "Proves local recovery of declared runtime authorities and state reconstruction. It does not prove external service availability or upstream recognition.",
    }
    OUT.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    # Regenerate once more with the final PASS/FAIL proof materialized, so the
    # authoritative stack snapshot describes the post-recovery steady state.
    post_export = export_state_with_retry()
    post_state = read_json(STATE)
    proof["postProofSnapshot"] = {
        "exportReturnCode": post_export.returncode,
        "state": post_state.get("state"),
        "externalState": post_state.get("external_state"),
        "freshness": post_state.get("freshness_status"),
    }
    if proof["status"] == "PASS" and post_state.get("state") != "healthy":
        proof["status"] = "FAIL"
        proof["checks"]["stack_returned_healthy"] = False
        OUT.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
        export_state_with_retry()
    else:
        OUT.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    return proof


def main() -> int:
    execute = "--execute" in sys.argv
    if not execute:
        proof = read_json(OUT)
        print(json.dumps(proof or {"status": "MISSING", "path": str(OUT)}, indent=2))
        return 0 if proof else 2
    try:
        proof = execute_rehearsal()
    except Exception as exc:
        proof = {
            "schema": "flop.cold-boot-recovery-proof/v1", "finishedAt": now(),
            "status": "FAIL", "error": f"{type(exc).__name__}: {exc}",
            "claimBoundary": "Recovery rehearsal failed; no completed recovery claim.",
        }
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
        # Always attempt restoration if the rehearsal failed after stopping an owner.
        for name in ("TechnocoreProbeAgent", "FLOPUnifiedObservatory", "FLOPUsefulWorkOperatorWatchdog"):
            task("RUN", name)
        export_state_with_retry()
    print(json.dumps(proof, indent=2))
    return 0 if proof["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
