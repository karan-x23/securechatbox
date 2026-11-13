import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class PresenceAndSeenTests(unittest.TestCase):
    def test_registered_participant_is_reported_offline_after_socket_closes(self):
        room = "a" * 32
        alice, bob = "b" * 32, "c" * 32
        with tempfile.TemporaryDirectory() as temp, patch.object(app, "DB_PATH", str(Path(temp) / "chat.sqlite3")):
            app.init_db()
            with app.db() as conn:
                conn.execute("INSERT INTO rooms VALUES(?,?,?)", (room, "verifier", 1.0))
                conn.execute("INSERT INTO participants(room_id, participant_id, display_name, first_seen, last_seen) VALUES(?,?,?,?,?)", (room, alice, "Alice", 1.0, 1.0))
                conn.execute("INSERT INTO participants(room_id, participant_id, display_name, first_seen, last_seen) VALUES(?,?,?,?,?)", (room, bob, "Bob", 1.0, 1.0))
            app.room_sockets[room] = {alice: object()}
            presence = {p["id"]: p["online"] for p in app._presence(room)}
            self.assertTrue(presence[alice])
            self.assertFalse(presence[bob])
            app.room_sockets.pop(room, None)

    def test_heartbeat_timeout_is_defined_for_idle_mobile_tabs(self):
        self.assertGreaterEqual(app.HEARTBEAT_TIMEOUT, 60)


class MobileAndReadReceiptUiTests(unittest.TestCase):
    def setUp(self):
        self.html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")

    def test_read_receipts_require_focused_visible_chat_and_visible_message(self):
        self.assertIn("document.visibilityState==='visible'", self.html)
        self.assertIn("document.hasFocus()", self.html)
        self.assertIn("visibleHeight/denominator>=0.6", self.html)
        self.assertIn("sendReceipt('delivered',id)", self.html)
        self.assertNotIn("if(document.visibilityState==='visible')sendReceipt('read',id)", self.html)

    def test_online_and_offline_presence_labels_are_available(self):
        self.assertIn("other.online?' · Online':' · Offline'", self.html)
        self.assertIn("value.includes('offline')?'offline'", self.html)

    def test_mobile_layout_uses_safe_areas_and_large_touch_targets(self):
        self.assertIn("@media(max-width:720px)", self.html)
        self.assertIn("100dvh", self.html)
        self.assertIn("env(safe-area-inset-bottom)", self.html)
        self.assertIn("min-height:49px", self.html)
        self.assertIn("overscroll-behavior:contain", self.html)


if __name__ == "__main__":
    unittest.main()
