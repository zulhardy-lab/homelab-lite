"""Unit tests for the dashboard: run with  python3 -m unittest discover -s apps/dashboard/tests -v"""
import sys
import tempfile
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

    def test_runner_detail_matches_its_state(self):
        for runner, detail in (("idle", "waiting for a job"), ("busy", "running a job"), ("stopped", "isn't running")):
            s = main.summarise(status(), {"runner": runner, "time": NOW - 5}, NOW)
            row = next(c for c in s["components"] if c[0] == "GitHub runner on ci01")
            self.assertIn(detail, row[2])
        s = main.summarise(status(), {"runner": "idle", "time": NOW - 5}, NOW)
        row = next(c for c in s["components"] if c[0] == "GitHub runner on ci01")
        self.assertNotIn("running a job", row[2])

    def test_uptime_shows_seconds(self):
        self.assertEqual(main.duration(2 * 3600 + 30 * 60 + 7), "2 h 30 min 7 s")
        self.assertEqual(main.duration(3 * 86400 + 3600 + 120), "3 d 1 h 2 min")
        s = main.summarise(status(host={"uptime_s": 9007}), None, NOW)
        self.assertIn("up 2 h 30 min 7 s", s["components"][0][2])


class DeployLogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_dir = main.STATUS_DIR
        main.STATUS_DIR = Path(self.tmp.name)

    def tearDown(self):
        main.STATUS_DIR = self.old_dir
        self.tmp.cleanup()

    def test_missing_log(self):
        self.assertIsNone(main.load_log())

    def test_keeps_only_the_last_lines(self):
        (main.STATUS_DIR / "deploy.log").write_text("".join(f"line {i}\n" for i in range(100)), encoding="utf-8")
        lines = main.load_log()
        self.assertEqual(len(lines), main.LOG_LINES)
        self.assertEqual(lines[-1], "line 99")


class RenderTest(unittest.TestCase):
    def test_log_escaped_and_in_progress(self):
        s = main.summarise(status(), None, NOW, ["deploy of commit abc", "<b>pulling</b>"])
        live = main.render_live(s)
        self.assertIn("&lt;b&gt;pulling&lt;/b&gt;", live)
        self.assertIn("in progress", live)

    def test_log_finished(self):
        s = main.summarise(status(), None, NOW, ["deploy of commit abc", "2026-11-27T09:00:00Z finished, exit code 0"])
        self.assertNotIn("in progress", main.render_live(s))

    def test_no_log_yet(self):
        self.assertIn("No deploy log yet", main.render_live(main.summarise(status(), None, NOW)))

    def test_page_updates_itself_from_live(self):
        page = main.render(main.summarise(status(), None, NOW))
        self.assertIn('fetch("/live"', page)
        self.assertIn("Updates every second", page)


class PageTest(unittest.TestCase):
    def test_links_and_escaping(self):
        st = status(containers=[
            {"name": "<script>", "state": "running", "health": "healthy", "image": "x", "link": "http://a.nip.io"},
            {"name": "bad-link", "state": "running", "health": "healthy", "image": "x", "link": "javascript:alert(1)"},
        ])
        page = main.render(main.summarise(st, None, NOW))
        self.assertIn("&lt;script&gt;", page)
        self.assertEqual(page.count("<script>"), 1)  # only the page's own updater
        self.assertNotIn("<script>", main.render_live(main.summarise(st, None, NOW)))
        self.assertIn("href='http://a.nip.io'", page)
        self.assertNotIn("javascript:", page)

    def test_last_deploy_shown(self):
        page = main.render(main.summarise(status(), None, NOW))
        self.assertIn("abcdef123456", page)


if __name__ == "__main__":
    unittest.main()
