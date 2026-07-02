# AI Web Form Agent

A human-in-the-loop browser automation agent that fills web forms from natural language instructions and user profile data.

## Features

- Open target websites using Playwright
- Extract form fields dynamically
- Map user profile data to fields using rules or LLM
- Automatically fill forms
- Generate execution logs
- Capture screenshots
- Pause before final submission
- Provide a simple React dashboard

## Tech Stack

- Python
- FastAPI
- Playwright
- React
- Vite
- OpenAI API / Gemini API

## Demo Flow

1. User enters a website URL.
2. User enters a form-filling task.
3. User provides profile JSON.
4. Agent opens the webpage.
5. Agent extracts form fields.
6. Agent maps profile data to fields.
7. Agent fills the form.
8. Agent stops before submitting.
9. User reviews logs and screenshot.

## Limitations

- Does not solve CAPTCHA.
- Does not bypass login.
- Does not automate payment.
- Does not guarantee support for all websites.
- Does not auto-submit forms without approval.

