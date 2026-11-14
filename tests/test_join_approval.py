import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app


class JoinApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.object(app, "DB_PATH", str(Path(self.temp.name) / "chat.sqlite3"))
        self.patch.start()
        app.init_db()
        self.client = TestClient(app.app)
        self.client.__enter__()
        self.room_name = "Karan Private Chat"
        self.room_id = app.room_id_for_name(self.room_name)
        self.owner_id = "a" * 32
        self.owner_token = "A" * 43
        with app.db() as conn:
            conn.execute("INSERT INTO rooms(room_id,auth_hash,created_at) VALUES(?,?,?)",
                         (self.room_id, app.token_hash(self.owner_token), 1.0))
            conn.execute("INSERT INTO participants(room_id,participant_id,display_name,first_seen,last_seen) VALUES(?,?,?,?,?)",
                         (self.room_id, self.owner_id, "Owner", 1.0, 1.0))

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.patch.stop()
        self.temp.cleanup()

    def request_body(self, request_id="1" * 64, device_id="2" * 32, participant_id="3" * 32):
        public_key = app.base64.urlsafe_b64encode(b"\x04" + b"\x11" * 64).decode().rstrip("=")
        return {
            "room_name": self.room_name, "name": "Guest", "participant_id": participant_id,
            "device_id": device_id, "request_id": request_id, "public_key": public_key,
        }

    def test_request_is_persisted_and_duplicate_submission_is_idempotent(self):
        body = self.request_body()
        first = self.client.post("/api/rooms/join-request", json=body)
        second = self.client.post("/api/rooms/join-request", json=body)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["status"], "pending")
        self.assertEqual(second.json()["request_id"], first.json()["request_id"])
        with app.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) n FROM join_requests").fetchone()["n"], 1)

    def test_one_device_cannot_create_a_second_request(self):
        first = self.client.post("/api/rooms/join-request", json=self.request_body())
        second = self.client.post("/api/rooms/join-request", json=self.request_body(request_id="4" * 64))
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)

    def test_owner_authentication_is_required_to_list_or_decide(self):
        created = self.client.post("/api/rooms/join-request", json=self.request_body())
        listed = self.client.post("/api/rooms/join-requests/list", json={
            "room_id": self.room_id, "participant_id": self.owner_id, "auth_token": "B" * 43,
        })
        decision = self.client.post("/api/rooms/join-requests/decision", json={
            "room_id": self.room_id, "participant_id": self.owner_id, "auth_token": "B" * 43,
            "request_id": created.json()["request_id"], "decision": "reject",
        })
        self.assertEqual(listed.status_code, 403)
        self.assertEqual(decision.status_code, 403)

    def test_owner_can_see_pending_request_and_reject_it_once(self):
        created = self.client.post("/api/rooms/join-request", json=self.request_body())
        listed = self.client.post("/api/rooms/join-requests/list", json={
            "room_id": self.room_id, "participant_id": self.owner_id, "auth_token": self.owner_token,
        })
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["requests"][0]["name"], "Guest")
        rejected = self.client.post("/api/rooms/join-requests/decision", json={
            "room_id": self.room_id, "participant_id": self.owner_id, "auth_token": self.owner_token,
            "request_id": created.json()["request_id"], "decision": "reject",
        })
        self.assertEqual(rejected.status_code, 200)
        status = self.client.post("/api/rooms/join-request/status", json={
            "room_id": self.room_id, "request_id": created.json()["request_id"], "device_id": "2" * 32,
        })
        self.assertEqual(status.json()["status"], "rejected")

    def test_acceptance_is_encrypted_and_reserves_the_second_room_slot(self):
        body = self.request_body()
        created = self.client.post("/api/rooms/join-request", json=body)
        envelope = {"ephemeral_public_key": body["public_key"], "iv": "A" * 16, "data": "B" * 128}
        accepted = self.client.post("/api/rooms/join-requests/decision", json={
            "room_id": self.room_id, "participant_id": self.owner_id, "auth_token": self.owner_token,
            "request_id": created.json()["request_id"], "decision": "accept", "envelope": envelope,
        })
        self.assertEqual(accepted.status_code, 200)
        status = self.client.post("/api/rooms/join-request/status", json={
            "room_id": self.room_id, "request_id": created.json()["request_id"], "device_id": "2" * 32,
        })
        self.assertEqual(status.json()["status"], "accepted")
        self.assertEqual(status.json()["envelope"]["data"], envelope["data"])
        second = self.client.post("/api/rooms/join-request", json=self.request_body(
            request_id="5" * 64, device_id="6" * 32, participant_id="7" * 32))
        self.assertEqual(second.status_code, 409)
        approved_identity = self.client.post("/api/rooms/verify", json={
            "room_id": self.room_id, "auth_token": self.owner_token, "participant_id": "3" * 32,
        })
        other_identity = self.client.post("/api/rooms/verify", json={
            "room_id": self.room_id, "auth_token": self.owner_token, "participant_id": "7" * 32,
        })
        self.assertEqual(approved_identity.status_code, 200)
        self.assertEqual(other_identity.status_code, 409)

    def test_unknown_rooms_and_bad_public_keys_are_rejected(self):
        missing = self.request_body()
        missing["room_name"] = "Room Does Not Exist"
        self.assertEqual(self.client.post("/api/rooms/join-request", json=missing).status_code, 404)
        bad = self.request_body(request_id="8" * 64, device_id="9" * 32)
        bad["public_key"] = "not-a-public-key"
        self.assertEqual(self.client.post("/api/rooms/join-request", json=bad).status_code, 400)


class JoinApprovalUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")

    def test_request_button_and_pending_status_are_present(self):
        self.assertIn('id="requestJoin"', self.html)
        self.assertIn("Request to join this room", self.html)
        self.assertIn("No password needed to request access", self.html)
        self.assertIn("serverSubmitted", self.html)
        self.assertIn("Waiting for the room owner to approve it", self.html)

    def test_owner_accept_and_reject_flow_uses_secure_envelope(self):
        self.assertIn('id="joinRequestPanel"', self.html)
        self.assertIn("accept.textContent='Accept'", self.html)
        self.assertIn("Tap Accept to let this person join. No password needed.", self.html)
        self.assertIn("approvalRoomKeyBytes", self.html)
        self.assertIn("approvalWrappingKey", self.html)
        self.assertIn("await deriveBits(pass,roomId+':e2e:v1')", self.html)
        self.assertIn("Reject", self.html)
        self.assertIn("crypto.subtle.generateKey({name:'ECDH',namedCurve:'P-256'}", self.html)
        self.assertIn("SecureChatBox join approval v1:", self.html)
        self.assertIn("decision:'accept'", self.html)
        self.assertIn("decision:'reject'", self.html)

    def test_approved_requester_imports_room_key_and_joins_normally(self):
        self.assertIn("async function completeApprovedJoin", self.html)
        self.assertIn("record.privateKey,256", self.html)
        self.assertIn("key=await crypto.subtle.importKey('raw',roomKey", self.html)
        self.assertIn("connectSocket('join',currentAuthToken,currentRecoveryCode)", self.html)

    def test_private_request_key_is_kept_in_indexeddb(self):
        self.assertIn("indexedDB.open(REMEMBERED_DB_NAME,2)", self.html)
        self.assertIn("createObjectStore('joinRequests'", self.html)
        self.assertIn("async function readJoinRequestRecord", self.html)
        self.assertIn("async function writeJoinRequestRecord", self.html)


if __name__ == "__main__":
    unittest.main()
