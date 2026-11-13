import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp.name) / "chat.sqlite3")
        self.patch = patch.object(app, "DB_PATH", self.db_path)
        self.patch.start()
        app.init_db()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_ciphertext_round_trip_and_history_order(self):
        room, alice, bob = "a" * 32, "b" * 32, "c" * 32
        with app.db() as conn:
            conn.execute("INSERT INTO rooms VALUES(?,?,?)", (room, "verifier", 1.0))
            conn.execute("INSERT INTO participants VALUES(?,?,?,?,?)", (room, alice, "Alice", 1.0, 1.0))
            conn.execute("INSERT INTO participants VALUES(?,?,?,?,?)", (room, bob, "Bob", 1.0, 1.0))
            conn.execute("INSERT INTO messages(message_id,room_id,sender_id,ciphertext_json,client_message_id,created_at) VALUES(?,?,?,?,?,?)", ("m1", room, alice, json.dumps({"iv":"iv1","data":"cipher1"}), "1"*16, 2.0))
            conn.execute("INSERT INTO messages(message_id,room_id,sender_id,ciphertext_json,client_message_id,created_at) VALUES(?,?,?,?,?,?)", ("m2", room, bob, json.dumps({"iv":"iv2","data":"cipher2"}), "2"*16, 3.0))
            conn.execute("INSERT INTO receipts VALUES(?,?,?,?)", ("m1", bob, 4.0, 5.0))
        alice_history = app._history(room, alice)
        bob_history = app._history(room, bob)
        self.assertEqual([m["message_id"] for m in alice_history], ["m1", "m2"])
        self.assertEqual(alice_history[0]["payload"]["data"], "cipher1")
        self.assertTrue(bob_history[0]["delivered"])
        self.assertTrue(bob_history[0]["read"])
        self.assertFalse(alice_history[1]["delivered"])

    def test_token_hash_and_payload_validation(self):
        self.assertEqual(app.token_hash("token"), app.token_hash("token"))
        self.assertNotEqual(app.token_hash("token"), app.token_hash("different"))
        self.assertTrue(app._valid_payload({"iv":"abc", "data":"xyz"}))
        self.assertFalse(app._valid_payload({"iv":"abc"}))
        self.assertFalse(app._valid_payload({"iv":"x" * 65, "data":"ok"}))


class WebSocketFlowTests(unittest.TestCase):
    def test_two_person_message_receipts_and_reconnect_history(self):
        from fastapi.testclient import TestClient

        room = "d" * 32
        alice = "a" * 32
        bob = "b" * 32
        auth = "A" * 43  # test-only verifier-shaped token
        with tempfile.TemporaryDirectory() as temp, patch.object(app, "DB_PATH", str(Path(temp) / "chat.sqlite3")):
            with TestClient(app.app) as client:
                with client.websocket_connect(f"/ws/{room}") as ws_alice:
                    ws_alice.send_json({"type":"hello", "action":"create", "participant_id":alice, "name":"Alice", "auth_token":auth})
                    ready_a = ws_alice.receive_json()
                    self.assertEqual(ready_a["type"], "ready")
                    with client.websocket_connect(f"/ws/{room}") as ws_bob:
                        ws_bob.send_json({"type":"hello", "action":"join", "participant_id":bob, "name":"Bob", "auth_token":auth})
                        ready_b = ws_bob.receive_json()
                        self.assertEqual(ready_b["type"], "ready")
                        # Presence notification is sent to the already-connected peer.
                        self.assertEqual(ws_alice.receive_json()["type"], "presence")
                        ws_alice.send_json({"type":"message", "client_message_id":"f"*16, "payload":{"iv":"iv","data":"encrypted-payload"}})
                        ack = ws_alice.receive_json()
                        self.assertEqual(ack["type"], "message_ack")
                        incoming = ws_bob.receive_json()
                        self.assertEqual(incoming["type"], "message")
                        self.assertEqual(incoming["message_id"], ack["message_id"])
                        # A repeated send with the same client ID is idempotent in storage.
                        ws_alice.send_json({"type":"message", "client_message_id":"f"*16, "payload":{"iv":"different-iv","data":"different-ciphertext"}})
                        retry_ack = ws_alice.receive_json()
                        self.assertEqual(retry_ack["message_id"], ack["message_id"])
                        duplicate_live = ws_bob.receive_json()
                        self.assertEqual(duplicate_live["message_id"], ack["message_id"])
                        self.assertEqual(duplicate_live["payload"]["data"], "encrypted-payload")
                        ws_bob.send_json({"type":"delivered", "message_id":ack["message_id"]})
                        self.assertEqual(ws_alice.receive_json()["status"], "delivered")
                        ws_bob.send_json({"type":"read", "message_id":ack["message_id"]})
                        self.assertEqual(ws_alice.receive_json()["status"], "read")
                    # Bob's socket is now closed; reconnect with same participant ID.
                    with client.websocket_connect(f"/ws/{room}") as ws_bob_again:
                        ws_bob_again.send_json({"type":"hello", "action":"join", "participant_id":bob, "name":"Bob", "auth_token":auth})
                        ready_again = ws_bob_again.receive_json()
                        self.assertEqual(ready_again["type"], "ready")
                        self.assertEqual(len(ready_again["history"]), 1)
                        self.assertEqual(ready_again["history"][0]["client_message_id"], "f"*16)
                        self.assertTrue(ready_again["history"][0]["delivered"])
                        self.assertTrue(ready_again["history"][0]["read"])

    def test_offline_message_is_available_to_later_joiner(self):
        from fastapi.testclient import TestClient
        room = "9" * 32
        alice, bob, auth = "a" * 32, "b" * 32, "C" * 43
        with tempfile.TemporaryDirectory() as temp, patch.object(app, "DB_PATH", str(Path(temp) / "chat.sqlite3")):
            with TestClient(app.app) as client:
                with client.websocket_connect(f"/ws/{room}") as sender:
                    sender.send_json({"type":"hello", "action":"create", "participant_id":alice, "name":"Alice", "auth_token":auth})
                    self.assertEqual(sender.receive_json()["type"], "ready")
                    sender.send_json({"type":"message", "client_message_id":"9"*16, "payload":{"iv":"iv","data":"offline-ciphertext"}})
                    sent = sender.receive_json()
                    self.assertEqual(sent["type"], "message_ack")
                with client.websocket_connect(f"/ws/{room}") as receiver:
                    receiver.send_json({"type":"hello", "action":"join", "participant_id":bob, "name":"Bob", "auth_token":auth})
                    synced = receiver.receive_json()
                    self.assertEqual(len(synced["history"]), 1)
                    self.assertEqual(synced["history"][0]["payload"]["data"], "offline-ciphertext")
                    receiver.send_json({"type":"delivered", "message_id":sent["message_id"]})
                    receiver.send_json({"type":"read", "message_id":sent["message_id"]})
                with client.websocket_connect(f"/ws/{room}") as sender_again:
                    sender_again.send_json({"type":"hello", "action":"join", "participant_id":alice, "name":"Alice", "auth_token":auth})
                    restored = sender_again.receive_json()
                    self.assertTrue(restored["history"][0]["delivered"])
                    self.assertTrue(restored["history"][0]["read"])

    def test_room_rejects_third_participant_and_wrong_secret(self):
        from fastapi.testclient import TestClient
        room = "e" * 32
        with tempfile.TemporaryDirectory() as temp, patch.object(app, "DB_PATH", str(Path(temp) / "chat.sqlite3")):
            with TestClient(app.app) as client:
                with client.websocket_connect(f"/ws/{room}") as a:
                    a.send_json({"type":"hello", "action":"create", "participant_id":"1"*32, "name":"One", "auth_token":"A"*43})
                    self.assertEqual(a.receive_json()["type"], "ready")
                    with client.websocket_connect(f"/ws/{room}") as b:
                        b.send_json({"type":"hello", "action":"join", "participant_id":"2"*32, "name":"Two", "auth_token":"A"*43})
                        self.assertEqual(b.receive_json()["type"], "ready")
                        from starlette.websockets import WebSocketDisconnect
                        with client.websocket_connect(f"/ws/{room}") as c:
                            c.send_json({"type":"hello", "action":"join", "participant_id":"3"*32, "name":"Three", "auth_token":"A"*43})
                            with self.assertRaises(WebSocketDisconnect) as third_close:
                                c.receive_json()
                            self.assertEqual(third_close.exception.code, 1008)
                    from starlette.websockets import WebSocketDisconnect
                    with client.websocket_connect(f"/ws/{room}") as wrong:
                        wrong.send_json({"type":"hello", "action":"join", "participant_id":"4"*32, "name":"Wrong", "auth_token":"B"*43})
                        with self.assertRaises(WebSocketDisconnect) as bad_secret_close:
                            wrong.receive_json()
                        self.assertEqual(bad_secret_close.exception.code, 1008)


if __name__ == "__main__":
    unittest.main()