import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from core.config import load_config
from core.recovery import snapshot


def main():
    cfg = load_config()
    state = snapshot(cfg)
    out = ROOT / "FLOP_STACK_STATE.json"
    payload = json.dumps(state, indent=2) + "\n"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(payload, encoding="utf-8")
    try:
        os.replace(tmp, out)
    except PermissionError:
        out.write_text(payload, encoding="utf-8")
        try:
            tmp.unlink()
        except OSError:
            pass
    print(json.dumps({"ok": True, "path": str(out), "state": state.get("state")}, separators=(",", ":")))


if __name__ == "__main__":
    main()
