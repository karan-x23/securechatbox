import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app


class RecoveryCodeTests(unittest.TestCase):
    def test_recovery_code_restores_room_and_same_participant(self):
        room = "1" * 32
        participant = "2" * 32
        auth = "A" * 43
        recovery = "B" * 43
        with tempfile.TemporaryDirectory() as temp, patch.object(app, "DB_PATH", str(Path(temp) / "chat.sqlite3")):
            with TestClient(app.app) as client:
                with client.websocket_connect(f"/ws/{room}") as socket:
                    socket.send_json({
                        "type": "hello", "action": "create", "participant_id": participant,
                        "name": "Alex", "auth_token": auth, "recovery_code": recovery,
                    })
                    ready = socket.receive_json()
                    self.assertEqual(ready["type"], "ready")
                    self.assertTrue(ready["recovery_saved"])

                restored = client.post("/api/recover", json={"recovery_code": recovery})
                self.assertEqual(restored.status_code, 200)
                self.assertEqual(restored.headers["cache-control"], "no-store")
                self.assertEqual(restored.json(), {
                    "room_id": room, "participant_id": participant, "display_name": "Alex"
                })

    def test_invalid_and_unknown_recovery_codes_do_not_disclose_room_data(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(app, "DB_PATH", str(Path(temp) / "chat.sqlite3")):
            with TestClient(app.app) as client:
                invalid = client.post("/api/recover", json={"recovery_code": "short"})
                unknown = client.post("/api/recover", json={"recovery_code": "C" * 43})
                self.assertEqual(invalid.status_code, 400)
                self.assertEqual(unknown.status_code, 404)
                self.assertNotIn("room_id", unknown.json())

    def test_recovery_hash_is_stored_not_plaintext_code(self):
        room = "3" * 32
        participant = "4" * 32
        auth = "D" * 43
        recovery = "E" * 43
        with tempfile.TemporaryDirectory() as temp, patch.object(app, "DB_PATH", str(Path(temp) / "chat.sqlite3")):
            with TestClient(app.app):
                with app.db() as conn:
                    row = conn.execute(
                        "SELECT recovery_hash FROM participants WHERE room_id=? AND participant_id=?",
                        (room, participant),
                    ).fetchone()
                    self.assertIsNone(row)
                with TestClient(app.app) as client:
                    with client.websocket_connect(f"/ws/{room}") as socket:
                        socket.send_json({
                            "type": "hello", "action": "create", "participant_id": participant,
                            "name": "Sam", "auth_token": auth, "recovery_code": recovery,
                        })
                        socket.receive_json()
                    with app.db() as conn:
                        row = conn.execute(
                            "SELECT recovery_hash FROM participants WHERE room_id=? AND participant_id=?",
                            (room, participant),
                        ).fetchone()
                    self.assertIsNotNone(row)
                    self.assertNotEqual(row["recovery_hash"], recovery)
