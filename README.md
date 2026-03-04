# Proofreader — Self-Hosted Deployment

Your n8n workflow migrated to Python (FastAPI) + your existing HTML frontend.

## File structure

```
proofreader/
├── main.py            ← FastAPI backend (full pipeline)
├── requirements.txt
├── railway.toml       ← Railway config
├── Procfile           ← Render config
└── static/
    └── index.html     ← Your existing frontend (URLs already updated)
```

---

## Deploy to Railway (recommended — ~15 min)

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "initial"
   gh repo create proofreader --public --push   # or use GitHub web UI
   ```

2. **Create Railway project**
   - Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
   - Select your repo

3. **Add environment variables**
   - In Railway dashboard → Variables tab → Add:
     ```
     GROQ_API_KEY_VALIDATOR = your_validator_groq_key
     GROQ_API_KEY_FIXER     = your_fixer_groq_key
     ```

4. **Deploy** — Railway auto-detects Python and deploys.  
   Your app will be live at `https://your-app.up.railway.app`

---

## Deploy to Render (alternative)

1. Push to GitHub (same as above)
2. Go to [render.com](https://render.com) → New → Web Service → Connect repo
3. Set:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add environment variable: `GROQ_API_KEY = your_key`
5. Deploy

---

## Run locally (for testing)

```bash
# Install dependencies
pip install -r requirements.txt

# Set your Groq keys
export GROQ_API_KEY_VALIDATOR="your_validator_key"
export GROQ_API_KEY_FIXER="your_fixer_key"

# Start the server
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000` — your full app runs locally.

---

## Getting your Groq API key

1. Go to [console.groq.com](https://console.groq.com)
2. Sign in → API Keys → Create API Key
3. Copy and paste into the `GROQ_API_KEY` environment variable

---

## Model used

The app uses `llama-3.3-70b-versatile` by default (publicly available on Groq).  
If you have access to `openai/gpt-oss-120b` on Groq, update the `MODEL` constant in `main.py`:

```python
MODEL = "openai/gpt-oss-120b"
```

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/proofread` | JSON body: `{ "question": "..." }` |
| POST | `/proofread-file` | Multipart file upload (UTF-8 .txt) |
| GET | `/health` | Health check |
| GET | `/` | Frontend UI |
