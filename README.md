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
- OpenAI API or Gemini API

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

On Windows, avoid `uvicorn --reload` for Playwright-backed endpoints such as
`POST /tasks/{task_id}/analyze`. Uvicorn's reload subprocess uses an event loop
that cannot start Playwright's browser process, which raises
`NotImplementedError` from `asyncio.create_subprocess_exec`.

## LLM Field Mapping

Set one provider and its API key before starting the backend:

```powershell
# OpenAI (default)
$env:LLM_PROVIDER="openai"
$env:OPENAI_API_KEY="your-key"
$env:OPENAI_MODEL="gpt-5.5"

# Or Gemini
$env:LLM_PROVIDER="gemini"
$env:GEMINI_API_KEY="your-key"
$env:GEMINI_MODEL="gemini-2.5-flash"
```

Then call `POST /tasks/{task_id}/map-fields?mode=llm`. If configuration,
network access, provider output, or validation fails, the endpoint safely uses
the local rule mapper instead.

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
