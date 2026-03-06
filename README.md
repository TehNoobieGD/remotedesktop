# Remote Control Website (Phone -> PC)

This project gives you:
- A `FastAPI` web service (deploy on Render Web Service).
- A PC host page (`/pc`) to create a room and see connected phones.
- A mobile page (`/mobile`) with trackpad + full virtual keyboard (F keys, arrows, numpad, etc.) and QWERTY/AZERTY switch.
- A local `agent.py` you run on your PC to apply mouse/keyboard actions.

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
   python agent.py --server https://your-app.onrender.com --room ROOMCODE --password YOUR_PASSWORD
   ```
3. On phone browser, open `/mobile`, enter room code + password, then control via trackpad and keyboard.

## Notes

- Mobile users cannot create rooms, only join.
- Room password is per-room and never stored in plaintext (PBKDF2 hash).
- This controls your machine input. Use only on machines/accounts you own and trust.
