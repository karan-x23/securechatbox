import unittest
from pathlib import Path


class SoftPremiumFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(Path(__file__).resolve().parents[1]/"static"/"index.html").read_text(encoding="utf-8")

    def test_welcome_screen_uses_soft_personal_copy_and_heart_mark(self):
        self.assertIn('class="avatar" aria-hidden="true">♡</div>', self.html)
        self.assertIn("A little space.<br><span>Just for us.</span>", self.html)
        self.assertIn("A PRIVATE LITTLE CORNER", self.html)

    def test_soft_premium_theme_styles_setup_and_chat(self):
        self.assertIn("Soft, romantic premium theme", self.html)
        self.assertIn(".welcome h2 span", self.html)
        self.assertIn(".setup-card", self.html)
        self.assertIn(".msg.mine", self.html)
        self.assertIn(".composer", self.html)
        self.assertIn("prefers-reduced-motion:reduce", self.html)

    def test_existing_setup_and_chat_controls_are_preserved(self):
        for element_id in ("roomName","displayName","secret","create","connect","pairCodeInput","joinByPairCode","sendForm","emojiPicker","send"):
            self.assertIn(f'id="{element_id}"', self.html)


if __name__ == "__main__":
    unittest.main()
