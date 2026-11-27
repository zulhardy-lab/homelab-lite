#!/usr/bin/env python3
"""save-ci01-heartbeat: the ONLY thing ci01's heartbeat key can run on app01 (an SSH forced command,
set up by heartbeat.yml). Reads a tiny JSON message from ci01 and saves it as STATUS_DIR/ci01.json.

Whatever command ci01 asks for is ignored. The input is checked and trimmed to known fields, so the key
can't be used to write anything else, run anything else, or fill the disk.
"""
import json
import os
import sys
import tempfile
import time

STATUS_DIR = "/srv/homelab-lite/status"
RUNNER_STATES = {"busy", "idle", "stopped"}


def clean(raw):
    """Returns the message to save, or None if the input isn't a valid heartbeat."""
    try:
        msg = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(msg, dict) or msg.get("runner") not in RUNNER_STATES:
        return None
    return {"runner": msg["runner"], "time": time.time()}


def main():
    data = clean(sys.stdin.read(2048))
    if data is None:
        print("rejected: not a valid heartbeat", file=sys.stderr)
        return 1
    fd, tmp = tempfile.mkstemp(dir=STATUS_DIR, prefix=".ci01-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.chmod(tmp, 0o644)
    os.replace(tmp, os.path.join(STATUS_DIR, "ci01.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
