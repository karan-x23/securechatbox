import unittest
from pathlib import Path


class BackgroundPresenceUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")

    def test_hidden_app_tells_server_to_mark_participant_offline(self):
        self.assertIn("function pauseForBackground()", self.html)
        self.assertIn("type:'background'", self.html)
        self.assertIn("document.visibilityState==='hidden'", self.html)
        self.assertIn("window.addEventListener('pagehide',pauseForBackground)", self.html)

    def test_returning_to_foreground_reconnects_with_existing_session_credentials(self):
        self.assertIn("function resumeFromBackground()", self.html)
        self.assertIn("connectSocket('join',currentAuthToken,currentRecoveryCode)", self.html)
        self.assertIn("window.addEventListener('pageshow'", self.html)
        self.assertIn("window.addEventListener('focus'", self.html)

    def test_invite_url_is_not_permanently_displayed(self):
        self.assertNotIn('id="shareUrl"', self.html)
        self.assertNotIn('id="share"', self.html)
        self.assertIn('id="shareInvite"', self.html)
        self.assertIn("const url=location.href", self.html)
        self.assertIn("navigator.share", self.html)

    def test_messaging_controls_and_responsive_polish_remain(self):
        self.assertIn('id="sendForm"', self.html)
        self.assertIn('id="toggleRecovery"', self.html)
        self.assertIn("@media(max-width:720px)", self.html)
        self.assertIn("message-in", self.html)
