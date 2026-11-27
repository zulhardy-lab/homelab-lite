"""news: the top 5 headlines from one news feed (RSS or Atom), each linking to the full story.

Which feed: the NEWS_FEED_URL setting (deploy/compose.yml). The page names the source using the feed's own title.
Only headlines, times and links are shown; no article text is copied.

The feed is untrusted input from the internet:
  - parsed with defusedxml (protects against XML attacks such as entity expansion)
  - every text is HTML-escaped before it's shown, and only http/https links are kept
  - downloads are capped in size and time
The app fetches at most every REFRESH seconds and keeps the last good copy, so the page still works when the feed is
down. /health reports the app itself, not the feed: a news outage doesn't make the container unhealthy.
"""
import html
import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from defusedxml import ElementTree

FEED_URL = os.environ.get("NEWS_FEED_URL", "")
REFRESH = int(os.environ.get("NEWS_REFRESH_SECONDS", "900"))  # 15 minutes
PORT = int(os.environ.get("PORT", "8080"))
MAX_BYTES = 2 * 1024 * 1024
TOP = 5
ATOM = "{http://www.w3.org/2005/Atom}"


def safe_link(url):
    url = (url or "").strip()
    return url if url.startswith(("http://", "https://")) else ""


def text(element, path, ns=None):
    found = element.find(path, ns or {})
    return (found.text or "").strip() if found is not None and found.text else ""


def parse_feed(xml_bytes):
    """Returns {"source": str, "items": [{"title", "link", "time"}]} for an RSS 2.0 or Atom feed (top TOP items)."""
    root = ElementTree.fromstring(xml_bytes)
    items = []
    if root.tag == "rss":
        channel = root.find("channel")
        if channel is None:
            raise ValueError("RSS feed without a channel")
        source = text(channel, "title")
        for item in channel.findall("item"):
            items.append({"title": text(item, "title"), "link": safe_link(text(item, "link")), "time": text(item, "pubDate")})
    elif root.tag == f"{ATOM}feed":
        source = text(root, f"{ATOM}title")
        for entry in root.findall(f"{ATOM}entry"):
            link_el = entry.find(f"{ATOM}link[@rel='alternate']")
            if link_el is None:  # an Element with no children is falsy, so `or` can't be used here
                link_el = entry.find(f"{ATOM}link")
            link = link_el.get("href", "") if link_el is not None else ""
            items.append({"title": text(entry, f"{ATOM}title"), "link": safe_link(link),
                          "time": text(entry, f"{ATOM}updated") or text(entry, f"{ATOM}published")})
    else:
        raise ValueError(f"not an RSS or Atom feed (root element {root.tag!r})")
    items = [i for i in items if i["title"]][:TOP]
    return {"source": source or "Unknown source", "items": items}


def fetch(url):
    if not safe_link(url):
        raise ValueError("NEWS_FEED_URL must start with http:// or https://")
    req = urllib.request.Request(url, headers={"User-Agent": "homelab-lite-news/1.0 (learning lab)"})
    with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310: scheme checked above
        data = resp.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("feed is larger than 2 MB")
    return data


class Cache:
    """The last good copy of the feed, refreshed at most every REFRESH seconds."""

    def __init__(self):
        self.lock = threading.Lock()
        self.feed = None
        self.fetched_at = 0.0  # last attempt
        self.ok_at = 0.0  # last successful update
        self.error = ""

    def get(self, now=None):
        now = now or time.time()
        with self.lock:
            due = now - self.fetched_at >= REFRESH
            retry = self.feed is None and now - self.fetched_at >= 60  # no copy yet: retry every minute
            if due or retry:
                self.fetched_at = now
                try:
                    self.feed = parse_feed(fetch(FEED_URL))
                    self.ok_at = now
                    self.error = ""
                except Exception as exc:  # noqa: BLE001 - any failure keeps the last good copy
                    self.error = f"couldn't update the feed ({type(exc).__name__})"
            return self.feed, self.error


def render(feed, error, updated):
    e = html.escape
    if feed and feed["items"]:
        rows = "".join(
            f"<li class='headline'><a href='{e(i['link'])}'>{e(i['title'])}</a> <small>{e(i['time'])}</small></li>"
            if i["link"] else f"<li class='headline'>{e(i['title'])} <small>{e(i['time'])}</small></li>"
            for i in feed["items"]
        )
        body = f"<ol>{rows}</ol><p><small>Source: {e(feed['source'])}</small></p>"
    else:
        body = "<p>No headlines.....sad.</p>"
    note = f"<p class='note'>{e(error)}; showing the last good copy.</p>" if error and feed else (
        f"<p class='note'>{e(error)}.</p>" if error else "")
    stamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(updated)) if updated else "never"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Top very sad sad news headlines</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 48rem; padding: 0 1rem; color: #222; }}
li {{ margin: .6rem 0; }} small {{ color: #666; }} .note {{ color: #8a5a00; }}
</style></head><body>
<h1>Top {TOP} headlines in Asia and the World</h1>
{note}{body}
<p><small>Last updated {e(stamp)}. Headlines link to the original story.</small></p>
</body></html>"""


CACHE = Cache()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            self.reply(200, "text/plain", "ok\n")
        elif self.path in ("/", "/index.html"):
            feed, error = CACHE.get()
            self.reply(200, "text/html; charset=utf-8", render(feed, error, CACHE.ok_at))
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
