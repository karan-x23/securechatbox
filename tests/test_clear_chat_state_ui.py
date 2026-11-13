import unittest
from pathlib import Path


class ClearChatStateUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")

    def test_recovery_code_is_not_shown_automatically(self):
        self.assertIn("recoveryPanel', 'hidden'", self.html)
        self.assertIn("$('recoveryCode').classList.add('hidden')", self.html)
        self.assertIn("Show code", self.html)
        self.assertIn("$('closeRecovery').onclick", self.html)

    def test_waiting_state_explains_how_to_start_chat(self):
        self.assertIn("Waiting for your person to join", self.html)
        self.assertIn("They must use the same shared secret phrase", self.html)
        self.assertIn("You can send a message now", self.html)
        self.assertIn("Private room ready · share the invite link above", self.html)

    def test_chat_preserves_recovery_and_message_controls(self):
        self.assertIn('id="sendForm"', self.html)
        self.assertIn('id="toggleRecovery"', self.html)
        self.assertIn('id="copyRecovery"', self.html)
        self.assertIn('id="copy"', self.html)
        self.assertIn("@media(max-width:720px)", self.html)


if __name__ == "__main__":
    unittest.main()
