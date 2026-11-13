import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from core.config import load_config
from core.recovery import snapshot
from core.process_lock import writer_lock, WriterAlreadyRunning


def main():
    lock = ROOT / ".FLOP_STACK_STATE.lock"
    try:
        with writer_lock(lock):
            return export_state()
    except WriterAlreadyRunning as exc:
        raise SystemExit(str(exc))


def export_state():
    cfg = load_config()
    state = snapshot(cfg)
    out = ROOT / "FLOP_STACK_STATE.json"
    payload = json.dumps(state, indent=2) + "\n"
    tmp = ROOT / f".{out.name}.{os.getpid()}.tmp"
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    last_error = None
    for attempt in range(8):
        try:
            os.replace(tmp, out)
            last_error = None
            break
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.25 * (attempt + 1))
    write_mode = "atomic_replace"
    if last_error is not None:
        write_mode = "in_place_fallback"
        with out.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            tmp.unlink()
        except OSError:
            pass
    print(json.dumps({"ok": True, "path": str(out), "state": state.get("state"), "observed_at": state.get("observed_at"), "write_mode": write_mode}, separators=(",", ":")))


if __name__ == "__main__":
    main()
