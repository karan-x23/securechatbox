import unittest
from pathlib import Path


class PasswordFieldTests(unittest.TestCase):
    def test_password_has_no_fixed_minimum_and_is_nonempty_in_app_logic(self):
        html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="secret" type="password"', html)
        self.assertNotIn('minlength="12"', html)
        self.assertNotIn("pass.length<12", html)
        self.assertIn("if(pass.length===0)", html)

    def test_password_visibility_toggle_is_accessible_and_wired(self):
        html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="toggleSecret"', html)
        self.assertIn("secretInput.type=show?'text':'password'", html)
        self.assertIn("toggleSecret.setAttribute('aria-pressed',String(show))", html)
        self.assertIn("show?'Hide':'Show'", html)


if __name__ == "__main__":
    unittest.main()
