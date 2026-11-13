import unittest
from pathlib import Path


class FreshHomepageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")

    def test_home_page_disables_stale_browser_cache(self):
        self.assertIn('"Cache-Control": "no-store, max-age=0"', self.app)
        self.assertIn('"Pragma": "no-cache"', self.app)


if __name__ == "__main__":
    unittest.main()
