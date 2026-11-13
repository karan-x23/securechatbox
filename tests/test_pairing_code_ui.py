import unittest
from pathlib import Path


class PairingCodeUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")

    def test_homepage_has_join_by_pairing_code_without_url(self):
        self.assertIn('id="showPairCodeForm"', self.html)
        self.assertIn('id="pairCodeInput"', self.html)
        self.assertIn("fetch('/api/rooms/resolve'", self.html)
        self.assertIn("await start(false)", self.html)

    def test_invite_panel_shows_code_only_when_requested(self):
        self.assertIn('id="invitePanel" class="invite-panel hidden"', self.html)
        self.assertIn('id="pairCodeDisplay"', self.html)
        self.assertIn("formatPairCode(activePairCode)", self.html)
        self.assertIn("navigator.share", self.html)

    def test_private_link_is_not_persistently_visible(self):
        self.assertNotIn('id="shareUrl"', self.html)
        self.assertNotIn('id="share"', self.html)
        self.assertIn('id="shareInvite"', self.html)

    def test_chat_controls_and_background_presence_remain(self):
        self.assertIn('id="sendForm"', self.html)
        self.assertIn("function pauseForBackground()", self.html)
        self.assertIn("function resumeFromBackground()", self.html)
        self.assertIn("@media(max-width:720px)", self.html)


if __name__ == "__main__":
    unittest.main()
