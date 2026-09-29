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


def main():
    lock = ROOT / ".FLOP_STACK_STATE.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write(f"pid={os.getpid()}\nstarted={time.time()}\n")
    except FileExistsError:
        raise SystemExit("FLOP_STACK_STATE_WRITER_ALREADY_RUNNING")
    cfg = load_config()
    try:
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
        if last_error is not None:
            raise RuntimeError(f"ATOMIC_REPLACE_FAILED:{last_error}") from last_error
        print(json.dumps({"ok": True, "path": str(out), "state": state.get("state"), "observed_at": state.get("observed_at")}, separators=(",", ":")))
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
