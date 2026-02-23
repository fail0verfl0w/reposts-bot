import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
WATCHED_GUILD_IDS = set(int(x) for x in os.getenv("GUILD_IDS", "").split(",") if x)
IGNORED_CHANNEL_IDS = set(int(x) for x in os.getenv("IGNORED_CHANNELS", "").split(",") if x)
DB_PATH = os.getenv("DB_PATH", "reposts.db")
IMAGE_HASH_THRESHOLD = int(os.getenv("HASH_THRESHOLD", "8"))