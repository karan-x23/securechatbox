import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app


class PresenceDisconnectTests(unittest.TestCase):
    def test_other_participant_is_shown_offline_after_websocket_disconnect(self):
        room = "f" * 32
        alice, bob, auth = "a" * 32, "b" * 32, "D" * 43
        with tempfile.TemporaryDirectory() as temp, patch.object(app, "DB_PATH", str(Path(temp) / "chat.sqlite3")):
            with TestClient(app.app) as client:
                with client.websocket_connect(f"/ws/{room}") as ws_alice:
                    ws_alice.send_json({"type":"hello", "action":"create", "participant_id":alice, "name":"Alice", "auth_token":auth})
                    self.assertEqual(ws_alice.receive_json()["type"], "ready")

                    with client.websocket_connect(f"/ws/{room}") as ws_bob:
                        ws_bob.send_json({"type":"hello", "action":"join", "participant_id":bob, "name":"Bob", "auth_token":auth})
                        self.assertEqual(ws_bob.receive_json()["type"], "ready")
                        online = ws_alice.receive_json()
                        self.assertEqual(online["type"], "presence")
                        bob_state = next(p for p in online["participants"] if p["id"] == bob)
                        self.assertTrue(bob_state["online"])

                    offline = ws_alice.receive_json()
                    self.assertEqual(offline["type"], "presence")
                    bob_state = next(p for p in offline["participants"] if p["id"] == bob)
                    self.assertFalse(bob_state["online"])


    def test_background_packet_marks_participant_offline_immediately(self):
        room = "e" * 32
        alice, bob, auth = "c" * 32, "d" * 32, "F" * 43
        with tempfile.TemporaryDirectory() as temp, patch.object(app, "DB_PATH", str(Path(temp) / "chat.sqlite3")):
            with TestClient(app.app) as client:
                with client.websocket_connect(f"/ws/{room}") as ws_alice:
                    ws_alice.send_json({"type":"hello", "action":"create", "participant_id":alice, "name":"Alice", "auth_token":auth})
                    self.assertEqual(ws_alice.receive_json()["type"], "ready")
                    with client.websocket_connect(f"/ws/{room}") as ws_bob:
                        ws_bob.send_json({"type":"hello", "action":"join", "participant_id":bob, "name":"Bob", "auth_token":auth})
                        self.assertEqual(ws_bob.receive_json()["type"], "ready")
                        online = ws_alice.receive_json()
                        self.assertEqual(online["type"], "presence")
                        self.assertTrue(next(p for p in online["participants"] if p["id"] == bob)["online"])
                        ws_bob.send_json({"type":"background"})
                        offline = ws_alice.receive_json()
                        self.assertEqual(offline["type"], "presence")
                        self.assertFalse(next(p for p in offline["participants"] if p["id"] == bob)["online"])


if __name__ == "__main__":
    unittest.main()
