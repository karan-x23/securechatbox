import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app


class SearchDiscoveryTests(unittest.TestCase):
    def test_robots_and_sitemap_are_available(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(app, "DB_PATH", str(Path(temp) / "chat.sqlite3")):
                with TestClient(app.app) as client:
                    robots = client.get("/robots.txt")
                    self.assertEqual(robots.status_code, 200)
                    self.assertIn("Allow: /", robots.text)
                    self.assertIn("Disallow: /ws/", robots.text)
                    self.assertIn("/sitemap.xml", robots.text)

                    sitemap = client.get("/sitemap.xml")
                    self.assertEqual(sitemap.status_code, 200)
                    self.assertIn("application/xml", sitemap.headers["content-type"])
                    self.assertIn("https://securechatbox-ki63.onrender.com/", sitemap.text)


if __name__ == "__main__":
    unittest.main()
