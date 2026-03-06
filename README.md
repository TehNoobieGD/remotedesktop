# Remote Control Website (Phone -> PC)

This project gives you:
- A `FastAPI` web service (deploy on Render Web Service).
- A PC host page (`/pc`) to create a room and see connected phones.
- A mobile page (`/mobile`) with trackpad + full virtual keyboard (F keys, arrows, numpad, etc.), QWERTY/AZERTY switch, and live preview.
- A local `agent.py` you run on your PC to apply mouse/keyboard actions, stream preview at 30 FPS target, and stream system audio (no microphone).
- Multi-monitor support:
  - Auto-follow cursor across screens
  - Manual screen selection from mobile
  - Cursor overlay rendered on mobile preview

## Render Service Type

Use:
- `Web Service`
- `Python 3`

Build/start:
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Local Run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open:
- PC host: `http://127.0.0.1:8000/pc`
- Mobile UI: `http://127.0.0.1:8000/mobile`

## How To Use

1. On PC browser, open `/pc`, set PC name + room password, click `Create Room`.
2. On your PC terminal, run:
   ```bash
   pip install -r agent-requirements.txt
   python agent.py --server https://your-app.onrender.com --room ROOMCODE --password YOUR_PASSWORD --fps 30
   ```
3. On phone browser, open `/mobile`, enter room code + password, then control via trackpad and keyboard.
4. Rotate phone to landscape for best control layout (preview on top, keyboard left, trackpad right).
5. In `/pc`, enable room audio, then on mobile tap `Enable Audio` (browser requires a user tap).

## Electron Launcher (optional)

Created at:
- `C:\Users\clutc\OneDrive\Documents\Electron REMOTEDESKTOP`

Run it:
```bash
cd "C:\Users\clutc\OneDrive\Documents\Electron REMOTEDESKTOP"
npm install
npm start
```

It opens your hosted website and lets you start/stop `agent.py` from UI by entering server, room, and password.

Build Windows installer:
```bash
cd "C:\Users\clutc\OneDrive\Documents\Electron REMOTEDESKTOP"
npm run build-win
```

Output:
- `C:\Users\clutc\OneDrive\Documents\Electron REMOTEDESKTOP\dist\Electron RemoteDesktop Setup 1.0.0.exe`

## Notes

- Mobile users cannot create rooms, only join.
- Room password is per-room and never stored in plaintext (PBKDF2 hash).
- This controls your machine input. Use only on machines/accounts you own and trust.
