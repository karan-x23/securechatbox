import unittest
from pathlib import Path


class PasswordAutofillFixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(Path(__file__).resolve().parents[1]/"static"/"index.html").read_text(encoding="utf-8")

    def test_shared_password_field_does_not_use_current_password_autofill(self):
        self.assertIn('id="secret" type="password" name="securechat-room-shared-phrase" placeholder="Enter your shared password" autocomplete="new-password"', self.html)
        self.assertNotIn('id="secret" type="password" placeholder="Enter your shared password" autocomplete="current-password"', self.html)

    def test_create_and_join_set_distinct_autocomplete_modes(self):
        self.assertIn("function prepareSharedPhrase(mode)", self.html)
        self.assertIn("mode==='create'?'new-password':'off'", self.html)
        self.assertIn("prepareSharedPhraseMode('create');start(true)", self.html)
        self.assertIn("prepareSharedPhraseMode('join');start(false)", self.html)
        self.assertIn("prepareSharedPhraseMode('join');joinUsingPairCode()", self.html)
        self.assertIn("securechat-pair-join-phrase", self.html)

    def test_mismatch_error_explains_saved_password_autofill(self):
        self.assertIn("Your browser may have filled a saved password", self.html)
        self.assertIn("type the creator’s exact shared phrase yourself", self.html)

    def test_create_button_still_starts_room_creation(self):
        self.assertIn("prepareSharedPhraseMode('create');start(true)", self.html)
        self.assertIn("prepareSharedPhraseMode('join');start(false)", self.html)
        self.assertIn("prepareSharedPhraseMode('join');joinUsingPairCode()", self.html)
        self.assertIn('readonly', self.html)
        self.assertIn("secretInput.addEventListener('focus'", self.html)

    def test_pairing_and_chat_controls_remain(self):
        self.assertIn("fetch('/api/rooms/resolve'", self.html)
        self.assertIn("fetch('/api/rooms/verify'", self.html)
        self.assertIn('id="emojiPicker"', self.html)
        self.assertIn('id="sendForm"', self.html)


if __name__ == "__main__":
    unittest.main()
