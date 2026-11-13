import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import app


class PairingCodeTests(unittest.TestCase):
    def test_creator_receives_pairing_code_and_second_person_resolves_same_room(self):
        room = "a" * 32
        alice, bob, auth = "b" * 32, "c" * 32, "D" * 43
        with tempfile.TemporaryDirectory() as temp, patch.object(app, "DB_PATH", str(Path(temp) / "chat.sqlite3")):
            with TestClient(app.app) as client:
                with client.websocket_connect(f"/ws/{room}") as alice_socket:
                    alice_socket.send_json({
                        "type": "hello", "action": "create", "participant_id": alice,
                        "name": "Alice", "auth_token": auth
                    })
                    alice_ready = alice_socket.receive_json()
                    self.assertEqual(alice_ready["type"], "ready")
                    code = alice_ready["pair_code"]
                    self.assertRegex(code, r"^[A-HJ-NP-Z2-9]{16}$")

                    lookup = client.post("/api/rooms/resolve", json={"pair_code": code[:4] + "-" + code[4:8] + " " + code[8:]})
                    self.assertEqual(lookup.status_code, 200)
                    self.assertEqual(lookup.json()["room_id"], room)
                    self.assertEqual(lookup.headers["cache-control"], "no-store")

                    with client.websocket_connect(f"/ws/{lookup.json()['room_id']}") as bob_socket:
                        bob_socket.send_json({
                            "type": "hello", "action": "join", "participant_id": bob,
                            "name": "Bob", "auth_token": auth
                        })
                        bob_ready = bob_socket.receive_json()
                        self.assertEqual(bob_ready["type"], "ready")
                        self.assertEqual(bob_ready["pair_code"], code)
                        online = alice_socket.receive_json()
                        self.assertEqual(online["type"], "presence")
                        self.assertTrue(next(p for p in online["participants"] if p["id"] == bob)["online"])
                        alice_socket.send_json({
                            "type": "message", "client_message_id": "e" * 16,
                            "payload": {"iv": "iv", "data": "ciphertext"}
                        })
                        ack = alice_socket.receive_json()
                        incoming = bob_socket.receive_json()
                        self.assertEqual(incoming["type"], "message")
                        self.assertEqual(incoming["message_id"], ack["message_id"])

    def test_pairing_code_does_not_bypass_shared_secret(self):
        room = "d" * 32
        alice, auth = "e" * 32, "F" * 43
        with tempfile.TemporaryDirectory() as temp, patch.object(app, "DB_PATH", str(Path(temp) / "chat.sqlite3")):
            with TestClient(app.app) as client:
                with client.websocket_connect(f"/ws/{room}") as socket:
                    socket.send_json({"type": "hello", "action": "create", "participant_id": alice, "name": "Alice", "auth_token": auth})
                    ready = socket.receive_json()
                    result = client.post("/api/rooms/resolve", json={"pair_code": ready["pair_code"]})
                    self.assertEqual(result.status_code, 200)
                    with client.websocket_connect(f"/ws/{room}") as wrong:
                        wrong.send_json({"type": "hello", "action": "join", "participant_id": "1" * 32, "name": "Wrong", "auth_token": "G" * 43})
                        with self.assertRaises(WebSocketDisconnect) as closed:
                            wrong.receive_json()
                        self.assertEqual(closed.exception.code, 1008)

    def test_invalid_and_unknown_pairing_codes_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(app, "DB_PATH", str(Path(temp) / "chat.sqlite3")):
            with TestClient(app.app) as client:
                self.assertEqual(client.post("/api/rooms/resolve", json={"pair_code": "BAD"}).status_code, 400)
                unknown = client.post("/api/rooms/resolve", json={"pair_code": "A" * 16})
                self.assertEqual(unknown.status_code, 404)
                self.assertNotIn("room_id", unknown.json())

    def test_existing_room_can_get_a_pairing_code_on_next_join(self):
        room = "f" * 32
        auth, participant = "H" * 43, "2" * 32
        with tempfile.TemporaryDirectory() as temp, patch.object(app, "DB_PATH", str(Path(temp) / "chat.sqlite3")):
            with TestClient(app.app) as client:
                with client.websocket_connect(f"/ws/{room}") as socket:
                    socket.send_json({"type": "hello", "action": "create", "participant_id": participant, "name": "One", "auth_token": auth})
                    first = socket.receive_json()
                with client.websocket_connect(f"/ws/{room}") as socket:
                    socket.send_json({"type": "hello", "action": "join", "participant_id": participant, "name": "One", "auth_token": auth})
                    second = socket.receive_json()
                self.assertEqual(first["pair_code"], second["pair_code"])
