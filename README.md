# Proofreader

An AI-powered proofreading tool for coding questions. Paste or upload a question and get back a categorized error report (grammar and technical mistakes) alongside a fully corrected, properly formatted version — ready to publish.

---

## What it does

1. **Validates** the question against a strict style and formatting guide — catching grammar mistakes, structural issues, missing sections, incorrect headers, and formatting violations
2. **Fixes** only the reported errors, leaving everything else exactly as-is
3. **Returns** three outputs: grammar mistakes, technical mistakes, and the corrected question

---

## Tech stack

- **Frontend:** Vanilla HTML/CSS/JS with Markdown rendering
- **Backend:** Python (FastAPI)
- **AI:** Groq API — one model call for validation, one for fixing
- **Hosting:** Railway

---

## File structure

```
proofreader/
├── main.py            ← FastAPI backend
├── requirements.txt
├── railway.toml       ← Railway config
├── Procfile           ← Render config
└── static/
    └── index.html     ← Frontend
```

---

## Setup

### Environment variables

```
GROQ_API_KEY_VALIDATOR   ←  Groq key used for the validation step
GROQ_API_KEY_FIXER       ←  Groq key used for the fixing step
```

Get your keys at [console.groq.com](https://console.groq.com).

### Run locally

```bash
pip install -r requirements.txt

export GROQ_API_KEY_VALIDATOR="your_validator_key"
export GROQ_API_KEY_FIXER="your_fixer_key"

uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000`.

---

## Model

Defaults to `llama-3.3-70b-versatile`. To change it, update the `MODEL` constant in `main.py`:

```python
MODEL = "your-preferred-groq-model"
```

---

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/proofread` | JSON body: `{ "question": "..." }` |
| POST | `/proofread-file` | Multipart file upload (UTF-8 .txt, max 2 MB) |
| GET | `/health` | Health check |
| GET | `/` | Frontend UI |
