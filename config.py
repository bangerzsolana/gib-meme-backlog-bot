import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is required but not set.")

SEED_ADMIN = os.getenv("SEED_ADMIN", "")
GROUP_ID = os.getenv("GROUP_ID", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
