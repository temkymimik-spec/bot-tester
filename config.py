import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DATA_PATH = os.getenv("DATA_PATH", "data/bot_data.json")
MEDIA_DIR = os.getenv("MEDIA_DIR", "media")