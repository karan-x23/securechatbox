import unittest
from pathlib import Path


class EmojiPickerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")

    def test_picker_has_search_and_common_categories(self):
        self.assertIn('id="emojiPicker"', self.html)
        self.assertIn('id="emojiSearch"', self.html)
        for category in ("smileys", "animals", "food", "activities", "travel", "objects", "symbols"):
            self.assertIn(f'data-category="{category}"', self.html)

    def test_picker_inserts_at_cursor_and_preserves_message_send(self):
        self.assertIn("function insertEmoji(emoji)", self.html)
        self.assertIn("input.selectionStart", self.html)
        self.assertIn("input.setSelectionRange(caret,caret)", self.html)
        self.assertIn("input.dispatchEvent(new Event('input',{bubbles:true}))", self.html)
        self.assertIn("$('sendForm').addEventListener('submit'", self.html)

    def test_recent_emoji_is_saved_locally_and_picker_closes_accessibly(self):
        self.assertIn("securechat:recent-emoji", self.html)
        self.assertIn("setEmojiPicker(false)", self.html)
        self.assertIn("e.key==='Escape'", self.html)
        self.assertIn('aria-expanded="false"', self.html)

    def test_picker_respects_mobile_and_reduced_motion_preferences(self):
        self.assertIn(".emoji-picker{", self.html)
        self.assertIn("@media(max-width:720px)", self.html)
        self.assertIn("@media(prefers-reduced-motion:reduce){.emoji-picker{animation:none}}", self.html)


if __name__ == "__main__":
    unittest.main()
