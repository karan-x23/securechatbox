import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app


class VoiceNoteTests(unittest.TestCase):
    def test_encrypted_payload_limit_allows_voice_note_sized_messages(self):
        self.assertTrue(app._valid_payload({"iv": "a" * 16, "data": "x" * 430_000}))
        self.assertFalse(app._valid_payload({"iv": "a" * 16, "data": "x" * 450_001}))

    def test_large_encrypted_voice_note_payload_is_delivered_and_saved(self):
        room = "8" * 32
        alice, bob, auth = "a" * 32, "b" * 32, "V" * 43
        encrypted_audio_payload = {"iv": "i" * 16, "data": "c" * 120_000}
        with tempfile.TemporaryDirectory() as temp, patch.object(app, "DB_PATH", str(Path(temp) / "chat.sqlite3")):
            with TestClient(app.app) as client:
                with client.websocket_connect(f"/ws/{room}") as sender:
                    sender.send_json({"type": "hello", "action": "create", "participant_id": alice, "name": "Alice", "auth_token": auth})
                    self.assertEqual(sender.receive_json()["type"], "ready")
                    with client.websocket_connect(f"/ws/{room}") as receiver:
                        receiver.send_json({"type": "hello", "action": "join", "participant_id": bob, "name": "Bob", "auth_token": auth})
                        self.assertEqual(receiver.receive_json()["type"], "ready")
                        sender.receive_json()  # presence update
                        sender.send_json({"type": "message", "client_message_id": "f" * 16, "payload": encrypted_audio_payload})
                        ack = sender.receive_json()
                        incoming = receiver.receive_json()
                        self.assertEqual(ack["type"], "message_ack")
                        self.assertEqual(incoming["type"], "message")
                        self.assertEqual(incoming["payload"], encrypted_audio_payload)

    def test_chat_ui_records_previews_and_sends_encrypted_audio(self):
        html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="voiceRecord"', html)
        self.assertIn('id="voicePreviewPanel"', html)
        self.assertIn('id="sendVoiceNote"', html)
        self.assertIn("navigator.mediaDevices.getUserMedia", html)
        self.assertIn("MAX_VOICE_DURATION_SECONDS=30", html)
        self.assertIn("MAX_VOICE_BYTES=240*1024", html)
        self.assertIn("const payload=await encrypt(voiceMessage)", html)
        self.assertIn("if(obj.kind==='voice'", html)
        self.assertIn("audio.controls=true", html)
        self.assertIn("stopVoiceRecording(true)", html)


if __name__ == "__main__":
    unittest.main()
