# Private Two-Person Chat

A small FastAPI + WebSocket chat prototype for two concurrent participants.

## Features
- Permanent room identifier in the URL fragment (`#` plus 32 hex characters).
- Two concurrent connections per room.
- Client-side AES-256-GCM encryption; key derived from a shared passphrase using PBKDF2-HMAC-SHA256 (310,000 iterations).
- Server relays ciphertext only and does not persist chat messages.
- Mobile-friendly browser UI.
- No push notification API. A short sound is attempted only when the page is running and audio has been unlocked by the user. Mobile browsers may suspend background tabs, so background sound is not guaranteed.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Open `http://127.0.0.1:8000`. Create a room, share the generated URL, and have the other participant open it. Both enter the same secret phrase (at least 12 characters).

## Deploy

A `render.yaml` is included for Render. Connect this repository to Render and deploy as a Web Service. Free-tier availability and sleep limits may change.

## Important limitations
- This is a prototype and has not undergone an independent security audit.
- The server does not authenticate the shared passphrase. Anyone with the room URL can attempt to occupy one of the two connection slots (denial-of-service risk).
- There is no message history or server-side persistence. Messages already shown on another device cannot be remotely erased.
- Browser history, screenshots, device access, and network metadata are outside this app's control.
- Do not use for highly sensitive communication.
