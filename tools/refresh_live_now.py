from __future__ import annotations
import json, os, tempfile, time
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.config import load_config
from core.public_snapshot import build

OUT = ROOT / "_live_now.json"

def main():
    cfg = load_config()
    snap = build(cfg)
    now = datetime.now(timezone.utc).isoformat()
    snap["observed_at"] = now
    snap["generated_at"] = now
    snap["freshness_age_seconds"] = 0
    snap["freshness_status"] = "fresh"
    payload = json.dumps(snap, indent=2) + "\n"
    json.loads(payload)
    fd, tmp = tempfile.mkstemp(prefix=OUT.name + ".", suffix=".tmp", dir=str(OUT.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())

        last_error = None
        for _ in range(10):
            try:
                os.replace(tmp, OUT)
                last_error = None
                break
            except PermissionError as exc:
                last_error = exc
                time.sleep(0.1)

        if last_error is not None:
            # Windows can deny atomic replacement while a reader keeps the
            # destination open. Fall back to an fsynced in-place refresh so
            # the public snapshot cannot remain stale indefinitely.
            with OUT.open("w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

if __name__ == "__main__":
    main()
