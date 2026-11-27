"""Unit tests for example-data: run with  python3 -m unittest discover -s apps/example-data/tests -v"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main  # noqa: E402


class DataTest(unittest.TestCase):
    def test_data_file_is_valid(self):
        data = main.load_data()
        self.assertTrue(data["title"])
        self.assertTrue(data["rows"])
        for row in data["rows"]:
            for column in data["columns"]:
                self.assertIn(column, row)

    def test_page_shows_every_row(self):
        data = main.load_data()
        page = main.render(data)
        for row in data["rows"]:
            self.assertIn(main.html.escape(str(row[data["columns"][0]])), page)

    def test_escaping(self):
        page = main.render({"title": "<b>", "columns": ["a"], "rows": [{"a": "<script>"}]})
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)


if __name__ == "__main__":
    unittest.main()
