"""example-data: a webpage that serves a small table from data.json.

This is the template for your own apps: copy the folder, change data.json (or main.py), add the app to
deploy/compose.yml and deploy/Caddyfile, and open a pull request (docs/SETUP.md, Part 10).
"""
import html
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DATA_FILE = Path(os.environ.get("DATA_FILE", Path(__file__).with_name("data.json")))
PORT = int(os.environ.get("PORT", "8080"))


def load_data(path=DATA_FILE):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def render(data):
    e = html.escape
    columns = data["columns"]
    head = "".join(f"<th>{e(c)}</th>" for c in columns)
    body = "".join("<tr>" + "".join(f"<td>{e(str(row.get(c, '')))}</td>" for c in columns) + "</tr>" for row in data["rows"])
    source = data.get("source", {})
    src_url = source.get("url", "")
    src_html = (f"<p><small>Source: <a href='{e(src_url)}'>{e(source.get('name', src_url))}</a></small></p>"
                if src_url.startswith(("http://", "https://")) else "")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(data["title"])}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 48rem; padding: 0 1rem; color: #222; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ text-align: left; padding: .45rem .6rem; border-bottom: 1px solid #ddd; }}
small {{ color: #666; }}
</style></head><body>
<h1>{e(data["title"])}</h1>
<table><tr>{head}</tr>{body}</table>
{src_html}
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            self.reply(200, "text/plain", "ok\n")
        elif self.path in ("/", "/index.html"):
            self.reply(200, "text/html; charset=utf-8", render(load_data()))
        elif self.path == "/data.json":
            self.reply(200, "application/json", json.dumps(load_data()))
        else:
            self.reply(404, "text/plain", "not found\n")

    def reply(self, code, ctype, body):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()  # nosec B104: inside the container only
