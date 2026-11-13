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

    def test_private_actions_are_available_from_discreet_chat_menu(self):
        self.assertIn('id="chatMenuToggle"', self.html)
        self.assertIn('id="chatMenu" class="chat-menu hidden"', self.html)
        self.assertIn('id="shareInvite" class="menu-item hidden"', self.html)
        self.assertIn('id="toggleRecovery" class="menu-item"', self.html)
        self.assertNotIn('class="chat-tools"', self.html)
        self.assertIn("function closeChatMenu()", self.html)
        self.assertIn("aria-expanded", self.html)

    def test_conversation_polish_keeps_accessible_mobile_and_reduced_motion_styles(self):
        self.assertIn(".chat-menu", self.html)
        self.assertIn(".msg.mine", self.html)
        self.assertIn(".composer #send", self.html)
        self.assertIn("@media(max-width:720px)", self.html)
        self.assertIn("prefers-reduced-motion:reduce", self.html)

    def test_existing_setup_and_chat_controls_are_preserved(self):
        for element_id in ("roomName","displayName","secret","create","connect","pairCodeInput","joinByPairCode","sendForm","emojiPicker","send"):
            self.assertIn(f'id="{element_id}"', self.html)


if __name__ == "__main__":
    unittest.main()
