"""Unit tests for the dashboard: run with  python3 -m unittest discover -s apps/dashboard/tests -v"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main  # noqa: E402

NOW = 1_800_000_000.0


def status(**extra):
    data = {
        "time": NOW - 10,
        "host": {"uptime_s": 7200, "load_1m": 0.25, "cpus": 2, "mem_total": 2 * 1024**3,
                 "mem_available": 1024**3, "disk_total": 20 * 1024**3, "disk_used": 5 * 1024**3},
        "docker": "running",
        "containers": [
            {"name": "news", "state": "running", "health": "healthy", "image": "x:1", "link": "http://news.1.2.3.4.nip.io"},
            {"name": "caddy", "state": "running", "health": "no check", "image": "caddy", "link": None},
        ],
        "last_deploy": {"commit": "abcdef1234567890", "time": "2026-11-27T09:00:00Z"},
    }
    data.update(extra)
    return data


def states(summary):
    return {name: state for name, state, _ in summary["components"]}


class SummariseTest(unittest.TestCase):
    def test_everything_fresh(self):
        s = main.summarise(status(), {"runner": "idle", "time": NOW - 5}, NOW)
        self.assertEqual(states(s), {
            "app01": "up", "Docker on app01": "running", "ci01": "up",
            "GitHub runner on ci01": "idle", "Status collector": "running",
        })
        self.assertEqual(len(s["containers"]), 2)

    def test_no_heartbeat_means_ci01_down(self):
        s = main.summarise(status(), {"runner": "idle", "time": NOW - 300}, NOW)
        self.assertEqual(states(s)["ci01"], "down")
        self.assertEqual(states(s)["GitHub runner on ci01"], "unknown")

    def test_stale_status_hides_containers(self):
        s = main.summarise(status(time=NOW - 300), None, NOW)
        self.assertEqual(states(s)["app01"], "unknown")
        self.assertEqual(states(s)["Status collector"], "stopped")
        self.assertEqual(s["containers"], [])

    def test_missing_files(self):
        s = main.summarise(None, None, NOW)
        self.assertEqual(states(s)["Status collector"], "stopped")


class RenderTest(unittest.TestCase):
    def test_links_and_escaping(self):
        st = status(containers=[
            {"name": "<script>", "state": "running", "health": "healthy", "image": "x", "link": "http://a.nip.io"},
            {"name": "bad-link", "state": "running", "health": "healthy", "image": "x", "link": "javascript:alert(1)"},
        ])
        page = main.render(main.summarise(st, None, NOW))
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("<script>", page)
        self.assertIn("href='http://a.nip.io'", page)
        self.assertNotIn("javascript:", page)

    def test_last_deploy_shown(self):
        page = main.render(main.summarise(status(), None, NOW))
        self.assertIn("abcdef123456", page)


if __name__ == "__main__":
    unittest.main()
