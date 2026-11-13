import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app


class RoomAuthPreflightTests(unittest.TestCase):
    def test_correct_password_is_verified_before_websocket_join(self):
        room = "a" * 32
        alice = "b" * 32
        token = "C" * 43
        with tempfile.TemporaryDirectory() as temp, patch.object(app, "DB_PATH", str(Path(temp) / "chat.sqlite3")):
            with TestClient(app.app) as client:
                with client.websocket_connect(f"/ws/{room}") as socket:
                    socket.send_json({"type":"hello","action":"create","participant_id":alice,"name":"Alice","auth_token":token})
                    self.assertEqual(socket.receive_json()["type"],"ready")
                response = client.post("/api/rooms/verify",json={"room_id":room,"auth_token":token,"participant_id":"d"*32})
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json(),{"status":"verified"})
                self.assertEqual(response.headers["cache-control"],"no-store")

    def test_wrong_password_returns_clear_error_before_websocket(self):
        room = "e" * 32
        with tempfile.TemporaryDirectory() as temp, patch.object(app, "DB_PATH", str(Path(temp) / "chat.sqlite3")):
            with TestClient(app.app) as client:
                with client.websocket_connect(f"/ws/{room}") as socket:
                    socket.send_json({"type":"hello","action":"create","participant_id":"f"*32,"name":"Alice","auth_token":"G"*43})
                    socket.receive_json()
                response = client.post("/api/rooms/verify",json={"room_id":room,"auth_token":"H"*43,"participant_id":"1"*32})
                self.assertEqual(response.status_code,403)
                self.assertIn("shared password does not match",response.json()["detail"])

    def test_missing_room_and_full_room_are_reported_before_websocket(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(app, "DB_PATH", str(Path(temp) / "chat.sqlite3")):
            with TestClient(app.app) as client:
                missing = client.post("/api/rooms/verify",json={"room_id":"2"*32,"auth_token":"I"*43,"participant_id":"3"*32})
                self.assertEqual(missing.status_code,404)
                room="4"*32
                with client.websocket_connect(f"/ws/{room}") as a:
                    a.send_json({"type":"hello","action":"create","participant_id":"5"*32,"name":"A","auth_token":"J"*43})
                    a.receive_json()
                    with client.websocket_connect(f"/ws/{room}") as b:
                        b.send_json({"type":"hello","action":"join","participant_id":"6"*32,"name":"B","auth_token":"J"*43})
                        b.receive_json()
                        full=client.post("/api/rooms/verify",json={"room_id":room,"auth_token":"J"*43,"participant_id":"7"*32})
                        self.assertEqual(full.status_code,409)
                        self.assertIn("two participants",full.json()["detail"])
