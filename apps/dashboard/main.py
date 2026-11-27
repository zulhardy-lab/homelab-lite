"""homelab-lite dashboard: one page with the state of every part of the lab, and a link to each app.

It reads two files from STATUS_DIR (mounted read-only; this container never gets the Docker socket):
  status.json  app01, Docker, containers, last deploy   (written every 30 s by status-collector on app01)
  ci01.json    ci01 and its GitHub runner               (written every 30 s by ci01's heartbeat)
A file older than STALE_AFTER seconds counts as missing: its part of the lab shows as down or unknown.
"""
import html
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATUS_DIR = Path(os.environ.get("STATUS_DIR", "/status"))
STALE_AFTER = 90  # seconds
PORT = int(os.environ.get("PORT", "8080"))

GOOD = {"up", "running", "healthy", "idle", "busy"}
BAD = {"down", "stopped", "exited", "dead", "unhealthy"}


def load(name):
    try:
        return json.loads((STATUS_DIR / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def fresh(data, now):
    return bool(data) and isinstance(data.get("time"), (int, float)) and now - data["time"] <= STALE_AFTER


def gib(n):
    return f"{n / 1024**3:.1f} GB"


def duration(seconds):
    days, rest = divmod(int(seconds), 86400)
    hours, rest = divmod(rest, 3600)
    return f"{days} d {hours} h" if days else f"{hours} h {rest // 60} min"


def summarise(status, ci01, now):
    """Turns the two status files into what the page shows. Kept free of HTML so it can be unit-tested."""
    s_ok, c_ok = fresh(status, now), fresh(ci01, now)
    components = []

    if s_ok:
        h = status.get("host", {})
        detail = (f"up {duration(h.get('uptime_s', 0))} · load {h.get('load_1m', 0):.2f} on {h.get('cpus', 1)} CPUs · "
                  f"memory {gib(h.get('mem_total', 0) - h.get('mem_available', 0))} of {gib(h.get('mem_total', 0))} · "
                  f"disk {gib(h.get('disk_used', 0))} of {gib(h.get('disk_total', 0))}")
        components.append(("app01", "up", detail))
        components.append(("Docker on app01", status.get("docker", "down"), ""))
    else:
        components.append(("app01", "unknown", "no fresh status.json: is the status collector running?"))
        components.append(("Docker on app01", "unknown", ""))

    if c_ok:
        components.append(("ci01", "up", "heartbeat received"))
        components.append(("GitHub runner on ci01", ci01.get("runner", "unknown"), "busy = running a job"))
    else:
        components.append(("ci01", "down", f"no heartbeat for over {STALE_AFTER} s"))
        components.append(("GitHub runner on ci01", "unknown", "ci01 isn't reporting"))

    age = int(now - status["time"]) if status and isinstance(status.get("time"), (int, float)) else None
    components.append(("Status collector", "running" if s_ok else "stopped",
                       f"last update {age} s ago" if age is not None else "never"))

    containers = status.get("containers", []) if s_ok else []
    deploy = status.get("last_deploy") if s_ok else None
    return {"components": components, "containers": containers, "last_deploy": deploy}


def css_class(state):
    if state in GOOD:
        return "ok"
    if state in BAD:
        return "bad"
    return "warn"


def render(summary):
    e = html.escape
    rows = "".join(
        f"<tr><td>{e(name)}</td><td class='{css_class(state)}'>{e(state)}</td><td>{e(detail)}</td></tr>"
        for name, state, detail in summary["components"]
    )
    crow = []
    for c in summary["containers"]:
        link = c.get("link") or ""
        link_html = f"<a href='{e(link)}'>open app</a>" if link.startswith("http://") else ""
        crow.append(
            f"<tr><td>{e(c.get('name', ''))}</td><td class='{css_class(c.get('state', ''))}'>{e(c.get('state', ''))}</td>"
            f"<td class='{css_class(c.get('health', ''))}'>{e(c.get('health', ''))}</td>"
            f"<td><code>{e(c.get('image', ''))}</code></td><td>{link_html}</td></tr>"
        )
    containers = "".join(crow) or "<tr><td colspan='5'>No containers reported.</td></tr>"
    d = summary["last_deploy"]
    deploy = (f"Last deploy: commit <code>{e(str(d.get('commit', ''))[:12])}</code> at {e(str(d.get('time', '')))}"
              if isinstance(d, dict) else "No deploy recorded yet.")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="30">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>homelab-lite status</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 64rem; padding: 0 1rem; color: #222; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
th, td {{ text-align: left; padding: .45rem .6rem; border-bottom: 1px solid #ddd; vertical-align: top; }}
.ok {{ color: #13722c; font-weight: 600; }} .bad {{ color: #b3261e; font-weight: 600; }} .warn {{ color: #8a5a00; font-weight: 600; }}
small {{ color: #666; }}
</style></head><body>
<h1>homelab-lite status</h1>
<p><small>Refreshes every 30 seconds. {deploy}</small></p>
<h2>Lab</h2>
<table><tr><th>Component</th><th>State</th><th>Details</th></tr>{rows}</table>
<h2>Containers on app01</h2>
<table><tr><th>Name</th><th>State</th><th>Health</th><th>Image</th><th>Link</th></tr>{containers}</table>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (name required by http.server)
        if self.path == "/health":
            self.reply(200, "text/plain", "ok\n")
        elif self.path in ("/", "/index.html"):
            page = render(summarise(load("status.json"), load("ci01.json"), time.time()))
            self.reply(200, "text/html; charset=utf-8", page)
        else:
            self.reply(404, "text/plain", "not found\n")

    def reply(self, code, ctype, body):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        pass  # keep `docker logs` quiet: the page reloads every 30 s


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()  # nosec B104: inside the container only
