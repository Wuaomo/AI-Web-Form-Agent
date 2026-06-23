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

## Safety Boundaries

- Never auto-submit a form without user approval.
- Do not solve CAPTCHA or bypass login.
- Do not automate payments or purchases.

See [TASKS.md](TASKS.md) for the development roadmap and
[AGENT_RULES.md](AGENT_RULES.md) for project constraints.
