import unittest
from pathlib import Path


class RememberDeviceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(Path(__file__).resolve().parents[1]/"static"/"index.html").read_text(encoding="utf-8")

    def test_device_session_is_saved_after_successful_connection(self):
        ready=self.html.split("if(packet.type==='ready'){",1)[1].split("if(packet.type==='message')",1)[0]
        self.assertIn("saveRememberedDeviceSession()", ready)
        self.assertIn("encryptionKey:key", self.html)
        self.assertIn("credentialCipher", self.html)

    def test_saved_credentials_are_encrypted_and_password_is_not_persisted(self):
        self.assertIn("crypto.subtle.encrypt({name:'AES-GCM',iv},key,credentials)", self.html)
        self.assertIn("crypto.subtle.decrypt(", self.html)
        self.assertNotIn("localStorage.setItem('secureChatPassword'", self.html)
        self.assertNotIn("localStorage.setItem('securechat:password'", self.html)

    def test_same_link_or_last_room_resumes_automatically(self):
        self.assertIn("async function resumeRememberedDevice()", self.html)
        self.assertIn("const targetRoom=validRoom(location.hash.slice(1))?location.hash.slice(1):localStorage.getItem('secureChatRoom')", self.html)
        self.assertIn("connectSocket('join',saved.authToken,saved.recoveryCode)", self.html)
        self.assertIn("resumeRememberedDevice();", self.html)

    def test_forget_this_device_removes_only_the_saved_session(self):
        self.assertIn("async function forgetRememberedSession(targetRoom)", self.html)
        self.assertIn("await forgetRememberedSession(leavingRoom)", self.html)
        self.assertIn("This device has been forgotten.", self.html)
        self.assertIn("<strong>Forget this device</strong>", self.html)


if __name__ == "__main__":
    unittest.main()
