import os

from dotenv import load_dotenv

load_dotenv()

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN", "")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")

# LLM: any OpenAI-compatible endpoint. Default = Google Gemini free tier.
# Groq alternative: LLM_BASE_URL=https://api.groq.com/openai/v1,
#   LLM_MODEL_FAST=llama-3.1-8b-instant, LLM_MODEL_SMART=llama-3.3-70b-versatile
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get(
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
