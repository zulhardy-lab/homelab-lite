"""Unit tests for news: run with  python3 -m unittest discover -s apps/news/tests -v  (needs defusedxml installed)

The feed tests read nasa-sample.xml: a saved, trimmed copy of NASA's real news-release feed
(https://www.nasa.gov/news-release/feed/). NASA content is generally not subject to US copyright; credit: NASA.
The tests never go online, so they give the same result every run.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main  # noqa: E402

SAMPLE = Path(__file__).with_name("nasa-sample.xml")


class FeedTest(unittest.TestCase):
    def setUp(self):
        if not SAMPLE.exists():
            self.fail(f"{SAMPLE.name} is missing: save NASA's feed there (see the comment at the top of this file)")
        self.feed = main.parse_feed(SAMPLE.read_bytes())

    def test_source_named_from_the_feed(self):
        self.assertEqual(self.feed["source"], "NASA")

    def test_top_five_with_titles_and_links(self):
        self.assertEqual(len(self.feed["items"]), main.TOP)
        for item in self.feed["items"]:
            self.assertTrue(item["title"])
            self.assertTrue(item["link"].startswith("https://"))

    def test_page_shows_the_headlines(self):
        page = main.render(self.feed, "", 1_800_000_000)
        self.assertEqual(page.count("class='headline'"), main.TOP)
        self.assertIn("Source: NASA", page)


class SafetyTest(unittest.TestCase):
    def test_only_web_links_kept(self):
        self.assertEqual(main.safe_link("javascript:alert(1)"), "")
        self.assertEqual(main.safe_link(" https://example.org/a "), "https://example.org/a")

    def test_rejects_entity_expansion(self):
        bomb = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]><rss><channel><title>&b;</title></channel></rss>'
        with self.assertRaises(Exception):
            main.parse_feed(bomb)

    def test_feed_url_must_be_http(self):
        with self.assertRaises(ValueError):
            main.fetch("file:///etc/passwd")

    def test_keeps_last_good_copy_when_the_feed_fails(self):
        good = {"source": "S", "items": [{"title": "t", "link": "https://x", "time": ""}]}
        cache = main.Cache()
        cache.feed, cache.fetched_at, cache.ok_at = good, 0.0, 1.0
        original = main.fetch
        main.fetch = lambda url: (_ for _ in ()).throw(OSError("down"))
        try:
            feed, error = cache.get(now=main.REFRESH + 10)
        finally:
            main.fetch = original
        self.assertEqual(feed, good)
        self.assertIn("couldn't update", error)
        self.assertIn("last good copy", main.render(feed, error, cache.ok_at))


if __name__ == "__main__":
    unittest.main()
