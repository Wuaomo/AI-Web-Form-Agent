# AI Web Form Agent

A human-in-the-loop browser automation agent that fills web forms from user
profile data and pauses before final submission.

## Project Structure

```text
backend/    FastAPI, agent services, and Playwright automation
frontend/   React and Vite user interface
docs/       Architecture and project documentation
```

## Planned Stack

- Python, FastAPI, and Playwright
- React and Vite
- OpenAI API, Gemini API, or DeepSeek API

## Backend Setup

```powershell
cd backend
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Run the API from the `backend` directory:

```powershell
uvicorn app.main:app
```

## LLM Field Mapping

The frontend lets you choose which LLM provider to use for semantic field
mapping. Configure any provider you want available before starting the backend:

```powershell
# DeepSeek (default)
$env:LLM_PROVIDER="deepseek"
$env:DEEPSEEK_API_KEY="your-key"
$env:DEEPSEEK_MODEL="deepseek-v4-flash"

# OpenAI
$env:LLM_PROVIDER="openai"
$env:OPENAI_API_KEY="your-key"
$env:OPENAI_MODEL="gpt-4.1-mini"

# Gemini
$env:LLM_PROVIDER="gemini"
$env:GEMINI_API_KEY="your-key"
$env:GEMINI_MODEL="gemini-2.5-flash"
```

The Agent uses LLM mapping by default when the frontend calls
`POST /tasks/{task_id}/map-fields`. You can choose a provider with
`?mode=llm&provider=openai`, `?provider=gemini`, or `?provider=deepseek`.
Developers can still compare behavior with
`POST /tasks/{task_id}/map-fields?mode=rules`.

The backend exposes `GET /llm/providers` so the UI can show which providers are
configured and which environment variable is missing. If a selected provider has
no API key, the mapping endpoint returns a setup hint instead of silently using
the wrong model. If the selected provider is configured but the network request,
provider output, or validation fails, the mapper safely falls back to local
rules.

The LLM mapper can use derived profile keys for split-name forms:

- `first_name` and `last_name` are derived from the stored `full_name`.
- `full_name` is still used when the form asks for one combined name.

Try `backend/examples/llm-registration.html` for a form whose fields use labels
like `Given name`, `Family name`, and `Where can we reach you?`. That example is
designed to show why semantic LLM mapping is useful beyond the rule matcher.

## Frontend Setup

```powershell
cd frontend
npm install
npm run dev
```

The frontend uses `http://localhost:8000` by default. To use another backend,
copy `.env.example` to `.env.local` and change `VITE_API_BASE_URL`.

## Safety Boundaries

- Never auto-submit a form without user approval.
- Do not solve CAPTCHA or bypass login.
- Do not automate payments or purchases.

See [TASKS.md](TASKS.md) for the development roadmap and
[AGENT_RULES.md](AGENT_RULES.md) for project constraints.
