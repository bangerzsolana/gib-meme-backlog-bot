import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is required but not set.")

SEED_ADMIN = os.getenv("SEED_ADMIN", "")
GROUP_ID = os.getenv("GROUP_ID", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.getenv("R2_AK_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SK", "")
R2_BUCKET = os.getenv("R2_BUCKET", "backlog-board")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "")  # e.g. https://pub-xxxx.r2.dev
