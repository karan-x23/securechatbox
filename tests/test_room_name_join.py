import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app


class RoomNameJoinTests(unittest.TestCase):
    def test_room_name_normalization_is_case_and_space_insensitive(self):
        self.assertEqual(app.normalize_room_name("  Karan   Private Chat "), "karan private chat")
        self.assertEqual(app.room_id_for_name("Karan Private Chat"), app.room_id_for_name(" karan   private chat "))

    def test_room_id_is_stable_and_uses_only_32_hex_characters(self):
        expected = hashlib.sha256(b"securechatbox:room-name:v1:karan private chat").hexdigest()[:32]
        self.assertEqual(app.room_id_for_name("Karan Private Chat"), expected)
        self.assertRegex(app.room_id_for_name("Karan Private Chat"), r"^[a-f0-9]{32}$")

    def test_resolve_name_endpoint_validates_and_returns_stable_room_id(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(app, "DB_PATH", str(Path(temp) / "chat.sqlite3")):
            with TestClient(app.app) as client:
                first = client.post("/api/rooms/resolve-name", json={"room_name": "Karan Private Chat"})
                second = client.post("/api/rooms/resolve-name", json={"room_name": "  karan   private chat "})
                invalid = client.post("/api/rooms/resolve-name", json={"room_name": "!!"})
                self.assertEqual(first.status_code, 200)
                self.assertEqual(second.status_code, 200)
                self.assertEqual(first.json()["room_id"], second.json()["room_id"])
                self.assertEqual(first.headers["cache-control"], "no-store")
                self.assertEqual(invalid.status_code, 400)

    def test_two_people_can_join_by_room_name_and_password_without_invite(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(app, "DB_PATH", str(Path(temp) / "chat.sqlite3")):
            with TestClient(app.app) as client:
                identity = client.post("/api/rooms/resolve-name", json={"room_name": "Karan Private Chat"})
                room_id = identity.json()["room_id"]
                shared_token = "N" * 43
                alice_id, bob_id = "a" * 32, "b" * 32
                with client.websocket_connect(f"/ws/{room_id}") as creator:
                    creator.send_json({
                        "type": "hello", "action": "create", "participant_id": alice_id,
                        "name": "Alice", "auth_token": shared_token,
                    })
                    self.assertEqual(creator.receive_json()["type"], "ready")
                    verify = client.post("/api/rooms/verify", json={
                        "room_id": room_id, "auth_token": shared_token, "participant_id": bob_id,
                    })
                    self.assertEqual(verify.status_code, 200)
                    with client.websocket_connect(f"/ws/{room_id}") as joiner:
                        joiner.send_json({
                            "type": "hello", "action": "join", "participant_id": bob_id,
                            "name": "Bob", "auth_token": shared_token,
                        })
                        ready = joiner.receive_json()
                        self.assertEqual(ready["type"], "ready")
                        names = {person["name"] for person in ready["participants"]}
                        self.assertEqual(names, {"Alice", "Bob"})


if __name__ == "__main__":
    unittest.main()
