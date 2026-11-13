# SecureChatBox — two-person encrypted chat

A small FastAPI + WebSocket one-to-one chat. The server stores **encrypted message payloads only** in SQLite so a participant can reconnect and sync recent messages. The browser keeps the decryption key in memory; after a refresh, the user re-enters the shared secret phrase.

## Included behaviour

- One room, at most two registered participants.
- Room link is stable; the room code is kept in the URL fragment.
- A per-room participant ID lets the same browser reconnect after refresh. The user re-enters the secret phrase; the passphrase is not stored in local storage.
- Browser-side AES-256-GCM encryption; AES key and a separate room-access verifier are derived with PBKDF2-HMAC-SHA256 (310,000 iterations).
- Server stores ciphertext, not message plaintext or the AES key.
- SQLite message history (latest 200 are synced to the client on connect).
- Server acknowledgement, delivered/read receipts, online presence, typing indicator, application heartbeat, and automatic reconnect with backoff.
- No push notification API. Sound is attempted only while the page is open and audio has been enabled by a user gesture. Mobile browsers may suspend background tabs.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Run the automated tests with:

```bash
pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Open `http://127.0.0.1:8000`. Create a room, share the generated URL, and have the other participant join. Both participants must use the same secret phrase (at least 12 characters). Refreshing requires entering the phrase again; the existing participant ID and room are recovered automatically in that browser.

## Storage and deployment notes

- SQLite path is controlled by `DATABASE_PATH` (default `./data/securechatbox.sqlite3`).
- **For durable Render storage, attach a persistent disk and set `DATABASE_PATH` to a path on its mount**, such as `/var/data/securechatbox.sqlite3`. Without persistent storage, a redeploy or instance replacement can erase rooms and history.
- Set a long random `AUTH_PEPPER` environment variable before deployment. Keep it stable; changing it invalidates room authentication.
- Run a single application worker/instance with this SQLite + in-memory WebSocket presence implementation. Multiple workers/instances require shared PostgreSQL storage and a shared presence/pub-sub layer such as Redis.
- Back up the database file securely. It contains room identifiers, an authentication verifier, participant metadata, timestamps, and encrypted messages.

## Important limitations

This is an early implementation, not a WhatsApp replacement and not independently security-audited. The room-access verifier is a credential-equivalent bearer value sent over the TLS-protected WebSocket after client-side PBKDF2; use HTTPS/WSS in deployment and a strong, unique passphrase. Anyone who obtains the room link **and** the passphrase can join if a participant slot is available. The database can retain ciphertext indefinitely unless the operator deletes it; define a retention policy before production use. Browser screenshots, device access, and operating-system compromise are outside this app's control. Do not use it for highly sensitive communication until it has received a professional security review.