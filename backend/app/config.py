"""Application configuration."""

import os

APP_TITLE = "AI Web Form Agent API"
APP_VERSION = "0.1.0"

# Vite uses port 5173 by default. The 127.0.0.1 variants are included so
# either common local development hostname can access the API.
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# LLM field mapping is optional. When the selected provider is not configured
# or its request fails, the mapper automatically falls back to local rules.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
LLM_REQUEST_TIMEOUT_SECONDS = float(
    os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "30")
)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
