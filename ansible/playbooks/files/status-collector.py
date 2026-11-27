#!/usr/bin/env python3
"""status-collector: writes STATUS_DIR/status.json for the dashboard. Runs on app01 every 30 seconds
(systemd timer from status.yml), as the deploy user, which may talk to Docker.

The dashboard container never gets the Docker socket: it only reads this file, mounted read-only.

status.json:
  time         when this ran (seconds since 1970)
  host         app01: uptime, load, memory, disk
  docker       "running" or "down"
  containers   [{name, state, health, image, link}], link only for containers labelled homelab-lite.link
  last_deploy  what scripts/deploy.sh recorded in last-deploy.json, if anything
"""
import json
import os
import shutil
import subprocess
import tempfile
import time

STATUS_DIR = os.environ.get("STATUS_DIR", "/srv/homelab-lite/status")
APP01_IP = os.environ.get("APP01_IP", "")
LINK_LABEL = "homelab-lite.link"


def host_info():
    with open("/proc/uptime", encoding="ascii") as f:
        uptime = float(f.read().split()[0])
    with open("/proc/loadavg", encoding="ascii") as f:
        load1 = float(f.read().split()[0])
    mem = {}
    with open("/proc/meminfo", encoding="ascii") as f:
        for line in f:
            key, value = line.split(":", 1)
            mem[key] = int(value.split()[0]) * 1024
    disk = shutil.disk_usage("/")
    return {
        "uptime_s": int(uptime),
        "load_1m": load1,
        "cpus": os.cpu_count() or 1,
        "mem_total": mem.get("MemTotal", 0),
        "mem_available": mem.get("MemAvailable", 0),
        "disk_total": disk.total,
        "disk_used": disk.used,
    }


def parse_labels(text):
    labels = {}
    for part in (text or "").split(","):
        if "=" in part:
            key, value = part.split("=", 1)
            labels[key.strip()] = value.strip()
    return labels


def health_from_status(status):
    """Docker puts health in the status text, e.g. 'Up 5 minutes (healthy)'."""
    for word in ("unhealthy", "healthy", "health: starting"):
        if f"({word})" in status:
            return "starting" if word == "health: starting" else word
    return "no check"


def containers():
    """Returns (docker_state, [containers]). docker ps -a also lists stopped containers."""
    try:
        out = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{json .}}"],
            capture_output=True, text=True, timeout=20, check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return "down", []
    result = []
    for line in out.splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        labels = parse_labels(c.get("Labels", ""))
        link = None
        if labels.get(LINK_LABEL) and APP01_IP:
            link = f"http://{labels[LINK_LABEL]}.{APP01_IP}.nip.io"
        result.append({
            "name": c.get("Names", ""),
            "state": c.get("State", "unknown"),
            "health": health_from_status(c.get("Status", "")),
            "image": c.get("Image", ""),
            "link": link,
        })
    return "running", sorted(result, key=lambda r: r["name"])


def last_deploy():
    try:
        with open(os.path.join(STATUS_DIR, "last-deploy.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_atomically(path, data):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".status-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def main():
    docker_state, items = containers()
    write_atomically(os.path.join(STATUS_DIR, "status.json"), {
        "time": time.time(),
        "host": host_info(),
        "docker": docker_state,
        "containers": items,
        "last_deploy": last_deploy(),
    })


if __name__ == "__main__":
    main()
