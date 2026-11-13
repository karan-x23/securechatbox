import unittest
from pathlib import Path


class RoomNameJoinUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(Path(__file__).resolve().parents[1]/"static"/"index.html").read_text(encoding="utf-8")

    def test_setup_distinguishes_room_name_from_display_name(self):
        self.assertIn('id="roomName"', self.html)
        self.assertIn('id="displayName"', self.html)
        self.assertIn("Room name (same on both phones)", self.html)
        self.assertIn("Your name", self.html)

    def test_join_without_invite_resolves_room_name_then_verifies_password(self):
        self.assertIn("fetch('/api/rooms/resolve-name'", self.html)
        self.assertIn("Finding the private room", self.html)
        self.assertIn("fetch('/api/rooms/verify'", self.html)
        self.assertIn("Enter the room name shared by the creator", self.html)
        self.assertIn("Join with room name &amp; password", self.html)

    def test_old_saved_random_room_id_is_not_used_as_join_fallback(self):
        self.assertNotIn("location.hash.slice(1)||localStorage.getItem('secureChatRoom')", self.html)
        self.assertIn("localStorage.setItem(participantStorageKey(),participantId)", self.html)

    def test_pair_code_and_invite_flows_are_preserved(self):
        self.assertIn("await start(false)", self.html)
        self.assertIn("roomName').value='';", self.html)
        self.assertIn("validRoom(location.hash.slice(1))", self.html)
        self.assertIn("fetch('/api/rooms/resolve'", self.html)


if __name__ == "__main__":
    unittest.main()
