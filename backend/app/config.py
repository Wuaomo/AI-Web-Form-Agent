"""Application configuration."""

import os

APP_TITLE = "AI Web Form Agent API"
APP_VERSION = "0.1.0"


def _getenv_any(*names: str) -> str | None:
    """Return the first non-empty environment variable from a list of names."""

    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None

# Vite uses port 5173 by default. The 127.0.0.1 variants are included so
# either common local development hostname can access the API.
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# LLM field mapping is optional. The API exposes provider readiness so the
# frontend can guide users before a request is made.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").lower()
LLM_REQUEST_TIMEOUT_SECONDS = float(
    os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "30")
)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DEEPSEEK_API_KEY = _getenv_any("DEEPSEEK_API_KEY", "DEEPSEEKAPI")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

LLM_PROVIDER_DETAILS = {
    "openai": {
        "display_name": "OpenAI",
        "api_key_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_MODEL",
    },
    "gemini": {
        "display_name": "Gemini",
        "api_key_env": "GEMINI_API_KEY",
        "model_env": "GEMINI_MODEL",
    },
    "deepseek": {
        "display_name": "DeepSeek",
        "api_key_env": "DEEPSEEK_API_KEY",
        "api_key_alias_envs": ["DEEPSEEKAPI"],
        "model_env": "DEEPSEEK_MODEL",
    },
}
