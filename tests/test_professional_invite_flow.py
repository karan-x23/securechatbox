import unittest
from pathlib import Path


class ProfessionalInviteFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")

    def test_opening_a_room_link_prioritizes_join_not_create(self):
        self.assertIn("You've been invited", self.html)
        self.assertIn("Join this private chat", self.html)
        self.assertIn('createButton.classList.add(\'secondary\')', self.html)
        self.assertIn("Do not create a new room", self.html)

    def test_invite_share_explains_same_link_and_secret_phrase(self):
        self.assertIn("Join my private chat using the same shared secret phrase.", self.html)
        self.assertIn("same shared secret phrase", self.html)
        self.assertIn("navigator.share", self.html)

    def test_recovery_code_stays_hidden_until_requested(self):
        self.assertIn("$('recoveryPanel').classList.add('hidden')", self.html)
        self.assertIn("$('recoveryCode').classList.add('hidden')", self.html)
        self.assertIn("$('revealRecovery').onclick", self.html)

    def test_connection_states_explain_that_server_is_online_and_peer_may_be_absent(self):
        self.assertIn("Room connected · waiting for invite", self.html)
        self.assertIn("The other person has not joined this link yet", self.html)
        self.assertIn("Trying to reconnect", self.html)

    def test_core_chat_controls_and_mobile_layout_remain(self):
        self.assertIn('id="sendForm"', self.html)
        self.assertIn('id="shareInvite"', self.html)
        self.assertIn('id="toggleRecovery"', self.html)
        self.assertIn("@media(max-width:720px)", self.html)


if __name__ == "__main__":
    unittest.main()
