import unittest
from pathlib import Path


class RecoveryUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")

    def test_restore_flow_is_available_without_a_room_link(self):
        self.assertIn('id="restoreCode"', self.html)
        self.assertIn("fetch('/api/recover'", self.html)
        self.assertIn("localStorage.setItem(participantStorageKey(),participantId)", self.html)
        self.assertIn("Enter your shared secret phrase", self.html)

    def test_each_participant_gets_a_separate_recovery_code(self):
        self.assertIn("securechat:recovery:'+roomId", self.html)
        self.assertIn("crypto.getRandomValues(new Uint8Array(32))", self.html)
        self.assertIn("recovery_code:recoveryCode", self.html)
        self.assertIn('id="copyRecovery"', self.html)

    def test_ui_uses_responsive_light_design_and_preserves_chat_controls(self):
        self.assertIn("color-scheme:light", self.html)
        self.assertIn("@media(max-width:720px)", self.html)
        self.assertIn("env(safe-area-inset-bottom)", self.html)
        self.assertIn('id="sendForm"', self.html)
        self.assertIn('id="soundOn"', self.html)
        self.assertIn("min-height:49px", self.html)


if __name__ == "__main__":
    unittest.main()
