"""homelab-lite dashboard: one page with the state of every part of the lab, and a link to each app.

It reads three files from STATUS_DIR (mounted read-only; this container never gets the Docker socket):
  status.json  app01, Docker, containers, last deploy   (written every second by status-collector on app01)
  ci01.json    ci01 and its GitHub runner               (written every 30 s by ci01's heartbeat)
  deploy.log   output of the last deploy's pull + up    (written by scripts/deploy.sh while it runs)
A status file older than STALE_AFTER seconds counts as missing: its part of the lab shows as down or unknown.

The page updates itself every second: a small script fetches /live (the same tables, rendered here) and swaps it in.
"""
import html
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATUS_DIR = Path(os.environ.get("STATUS_DIR", "/status"))
STALE_AFTER = 90  # seconds
LOG_LINES = 40  # lines of deploy.log to show
LOG_MAX_BYTES = 64 * 1024  # read at most this much from the end of deploy.log
PORT = int(os.environ.get("PORT", "8080"))

GOOD = {"up", "running", "healthy", "idle", "busy"}
BAD = {"down", "stopped", "exited", "dead", "unhealthy"}
RUNNER_DETAIL = {
    "idle": "online, waiting for a job",
    "busy": "running a job",
    "stopped": "the runner service isn't running on ci01",
}


def load(name):
    try:
        return json.loads((STATUS_DIR / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def load_log(name="deploy.log"):
    """Returns the last LOG_LINES lines of a log in STATUS_DIR, or None if there isn't one."""
    try:
        with open(STATUS_DIR / name, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - LOG_MAX_BYTES))
            text = f.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    return text.splitlines()[-LOG_LINES:]


def fresh(data, now):
    return bool(data) and isinstance(data.get("time"), (int, float)) and now - data["time"] <= STALE_AFTER


def gib(n):
    return f"{n / 1024**3:.1f} GB"


def duration(seconds):
    days, rest = divmod(int(seconds), 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{days} d {hours} h {minutes} min" if days else f"{hours} h {minutes} min {secs} s"


def summarise(status, ci01, now, deploy_log=None):
    """Turns the status files into what the page shows. Kept free of HTML so it can be unit-tested."""
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
        runner = ci01.get("runner", "unknown")
        components.append(("GitHub runner on ci01", runner, RUNNER_DETAIL.get(runner, "")))
    else:
        components.append(("ci01", "down", f"no heartbeat for over {STALE_AFTER} s"))
        components.append(("GitHub runner on ci01", "unknown", "ci01 isn't reporting"))

    age = int(now - status["time"]) if status and isinstance(status.get("time"), (int, float)) else None
    components.append(("Status collector", "running" if s_ok else "stopped",
                       f"last update {age} s ago" if age is not None else "never"))

    containers = status.get("containers", []) if s_ok else []
    deploy = status.get("last_deploy") if s_ok else None
    return {"components": components, "containers": containers, "last_deploy": deploy, "deploy_log": deploy_log}


def css_class(state):
    if state in GOOD:
        return "ok"
    if state in BAD:
        return "bad"
    return "warn"


def render_live(summary):
    """The part of the page that changes: swapped in every second by the page's script."""
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
    lines = summary.get("deploy_log")
    if lines is None:
        log_note, log_text = "", "No deploy log yet: the next deploy writes one."
    else:
        done = any("finished, exit code" in line for line in lines[-3:])
        log_note = "" if done else " <span class='warn'>in progress</span>"
        log_text = "\n".join(lines)
    return f"""<p><small>Updates every second. {deploy}</small></p>
<h2>Lab</h2>
<table><tr><th>Component</th><th>State</th><th>Details</th></tr>{rows}</table>
<h2>Containers on app01</h2>
<table><tr><th>Name</th><th>State</th><th>Health</th><th>Image</th><th>Link</th></tr>{containers}</table>
<h2>Last deploy on app01{log_note}</h2>
<p><small>Images are built on GitHub's machines; this is app01 pulling them and replacing the containers.</small></p>
<pre class='term' id='term'>{e(log_text)}</pre>"""


def render(summary):
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<noscript><meta http-equiv="refresh" content="5"></noscript>
<meta name="viewport" content="width=device-width, initial-scale=1"><title>homelab-lite status</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 64rem; padding: 0 1rem; color: #222; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
th, td {{ text-align: left; padding: .45rem .6rem; border-bottom: 1px solid #ddd; vertical-align: top; }}
.ok {{ color: #13722c; font-weight: 600; }} .bad {{ color: #b3261e; font-weight: 600; }} .warn {{ color: #8a5a00; font-weight: 600; }}
small {{ color: #666; }}
.term {{ background: #111; color: #d6d6d6; padding: .8rem 1rem; border-radius: 6px; font-size: .85rem;
         max-height: 22rem; overflow: auto; white-space: pre-wrap; word-break: break-all; }}
</style></head><body>
<h1>homelab-lite status</h1>
<div id="live">{render_live(summary)}</div>
<script>
// Every second: fetch the tables and the deploy log, and swap them in. The log stays scrolled to the bottom
// unless you've scrolled up to read it. If a fetch fails, the last good copy stays on screen.
(function () {{
  const live = document.getElementById("live");
  async function tick() {{
    try {{
      const term = document.getElementById("term");
      const atBottom = !term || term.scrollHeight - term.scrollTop - term.clientHeight < 20;
      const top = term ? term.scrollTop : 0;
      const r = await fetch("/live", {{ cache: "no-store" }});
      if (r.ok) {{
        live.innerHTML = await r.text();
        const t = document.getElementById("term");
        if (t) t.scrollTop = atBottom ? t.scrollHeight : top;
      }}
    }} catch (err) {{ /* app01 unreachable for a moment: keep what's shown */ }}
    setTimeout(tick, 1000);
  }}
  const t = document.getElementById("term");
  if (t) t.scrollTop = t.scrollHeight;
  setTimeout(tick, 1000);
}})();
</script>
</body></html>"""


def current():
    return summarise(load("status.json"), load("ci01.json"), time.time(), load_log())


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (name required by http.server)
        if self.path == "/health":
            self.reply(200, "text/plain", "ok\n")
        elif self.path in ("/", "/index.html"):
            self.reply(200, "text/html; charset=utf-8", render(current()))
        elif self.path == "/live":
            self.reply(200, "text/html; charset=utf-8", render_live(current()))
        else:
            self.reply(404, "text/plain", "not found\n")

    def reply(self, code, ctype, body):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        pass  # keep `docker logs` quiet: every open page asks for /live once a second


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()  # nosec B104: inside the container only
