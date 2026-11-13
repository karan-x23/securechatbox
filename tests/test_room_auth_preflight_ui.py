import unittest
from pathlib import Path


class RoomAuthPreflightUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(Path(__file__).resolve().parents[1]/"static"/"index.html").read_text(encoding="utf-8")

    def test_join_checks_password_before_opening_websocket(self):
        self.assertIn("fetch('/api/rooms/verify'", self.html)
        self.assertIn("Checking the shared password", self.html)
        self.assertIn("Password verified. Connecting securely", self.html)
        self.assertIn("The pairing code found the room, but the shared password does not match", self.html)

    def test_pairing_code_still_uses_room_lookup_then_normal_join(self):
        self.assertIn("fetch('/api/rooms/resolve'", self.html)
        self.assertIn("await start(false)", self.html)
        self.assertIn("connectSocket(action,authToken,recoveryCode)", self.html)

    def test_existing_chat_features_remain(self):
        self.assertIn('id="sendForm"', self.html)
        self.assertIn('id="emojiPicker"', self.html)
        self.assertIn("function pauseForBackground()", self.html)
