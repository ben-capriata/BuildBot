import os
from pathlib import Path

from dotenv import load_dotenv

# Paths
BUILDBOT_DIR = Path.home() / ".buildbot"
DATA_DIR = BUILDBOT_DIR / "data"
PROMPTS_DIR = BUILDBOT_DIR / "prompts"
DB_PATH = DATA_DIR / "buildbot.db"
ENV_PATH = BUILDBOT_DIR / ".env"

load_dotenv(ENV_PATH)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USER_ID = int(os.getenv("TELEGRAM_USER_ID", "0"))

# LLM provider fallback chain
PROVIDERS = [
    {
        "name": "groq",
        "model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_API_KEY", ""),
    },
    {
        "name": "cerebras",
        "model": "llama-3.1-70b",
        "base_url": "https://api.cerebras.ai/v1",
        "api_key": os.getenv("CEREBRAS_API_KEY", ""),
    },
    {
        "name": "mistral",
        "model": "mistral-small-latest",
        "base_url": "https://api.mistral.ai/v1",
        "api_key": os.getenv("MISTRAL_API_KEY", ""),
    },
]

# Load system prompt
SYSTEM_PROMPT = ""
_prompt_file = PROMPTS_DIR / "build_hour.txt"
if _prompt_file.exists():
    SYSTEM_PROMPT = _prompt_file.read_text().strip()
