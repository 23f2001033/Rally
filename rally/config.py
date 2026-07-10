import os

from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default: str = "") -> str:
    # strip() guards against trailing spaces/newlines when secrets are pasted into a host UI.
    return os.environ.get(key, default).strip()


SLACK_BOT_TOKEN = _env("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = _env("SLACK_APP_TOKEN")
SLACK_SIGNING_SECRET = _env("SLACK_SIGNING_SECRET")


def missing_required() -> list[str]:
    """Names of the credentials that must be set for Rally to run."""
    required = {
        "SLACK_BOT_TOKEN": SLACK_BOT_TOKEN,
        "SLACK_APP_TOKEN": SLACK_APP_TOKEN,
        "SLACK_SIGNING_SECRET": SLACK_SIGNING_SECRET,
        "LLM_API_KEY": _env("LLM_API_KEY"),
    }
    return [k for k, v in required.items() if not v]

# LLM: any OpenAI-compatible endpoint. Default = Google Gemini free tier.
# Groq alternative: LLM_BASE_URL=https://api.groq.com/openai/v1,
#   LLM_MODEL_FAST=llama-3.1-8b-instant, LLM_MODEL_SMART=llama-3.3-70b-versatile
LLM_API_KEY = _env("LLM_API_KEY")
LLM_BASE_URL = _env(
    "LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
)
# Use Google's floating aliases so a model retirement never breaks us mid-hackathon.
MODEL_FAST = os.environ.get("LLM_MODEL_FAST", "gemini-flash-lite-latest")
MODEL_SMART = os.environ.get("LLM_MODEL_SMART", "gemini-flash-latest")

DB_PATH = os.environ.get("RALLY_DB_PATH", "rally.db")
SIMULATION = os.environ.get("RALLY_SIMULATION", "1") == "1"
COORDINATOR_IDS = {
    u.strip() for u in os.environ.get("RALLY_COORDINATOR_IDS", "").split(",") if u.strip()
}

# Outreach etiquette (see RALLY-REVIEW.md R3/R7)
OVER_INVITE_FACTOR = 1.5      # invite a buffer beyond `needed` since some decline
MAX_ASKS_PER_MONTH = 6        # per-volunteer ask cap
SIM_RESPONSE_DELAY_RANGE = (4, 18)   # seconds; simulated volunteers reply in this window
JOB_POLL_SECONDS = 3
