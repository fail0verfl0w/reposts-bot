# DejaVu Bot

A Discord bot that detects and flags reposted links and images in your server, replying to the reposter with a link to the original post.

## Features

- **URL repost detection** — catches duplicate links across all channels, stripping tracking parameters (`utm_*`, `fbclid`, etc.) so the same article shared with different tracking tags is still flagged
- **Image repost detection** — uses perceptual hashing (pHash) to detect duplicate images even if they've been resaved, resized, or recompressed
- **Shortlink resolution** — follows `t.co`, `bit.ly`, `youtu.be` etc. before comparing, so shortened and full URLs of the same link are treated as one
- **48-hour window** — only flags reposts within a 48-hour rolling window; older posts don't count
- **Auto cleanup** — database is pruned every 6 hours so it never grows unbounded

## Tech Stack

- **Python 3.12+**
- **discord.py** — Discord API wrapper
- **aiosqlite** — async SQLite for persistent storage
- **Pillow + imagehash** — image processing and perceptual hashing
- **aiohttp** — async HTTP for shortlink resolution and image fetching

## Project Structure
```
repost-bot/
├── detectors/
│   ├── __init__.py
│   ├── url_detector.py      # URL extraction, normalization, shortlink detection
│   └── image_detector.py    # Image downloading and perceptual hashing
├── bot.py                   # Main bot logic and event handlers
├── database.py              # SQLite schema and queries
├── config.py                # Environment variable loading
├── requirements.txt
├── .env.example
└── README.md
```

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/yourusername/repost-bot.git
cd repost-bot
```

**2. Create and activate a virtual environment**
```bash
python -m venv venv

# Windows
venv\Scripts\activate.bat

# Mac/Linux
source venv/bin/activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Configure environment variables**
```bash
cp .env.example .env
```
Then edit `.env` with your values:

| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Your bot token from the Discord Developer Portal |
| `GUILD_IDS` | Comma-separated server IDs to monitor |
| `IGNORED_CHANNELS` | Comma-separated channel IDs to ignore (optional) |
| `DB_PATH` | Path to SQLite database file (default: `reposts.db`) |
| `HASH_THRESHOLD` | Perceptual hash sensitivity 1-20 (default: `8`, lower = stricter) |

**5. Discord Developer Portal setup**
- Create an application at https://discord.com/developers/applications
- Under the **Bot** tab, enable all three **Privileged Gateway Intents**
- Invite the bot with scopes: `bot` and permissions: `Read Messages`, `Send Messages`, `Read Message History`

**6. Run the bot**
```bash
python bot.py
```

## How It Works

When a message is posted the bot first checks for URLs, normalizing them by stripping tracking parameters and resolving shortlinks before comparing against the database. If no URL repost is found it then checks for image attachments and embed thumbnails, computing a perceptual hash for each and comparing against stored hashes using hamming distance. If a match is found within the threshold, the bot replies to the reposter tagging the original post.

## License

MIT
```

---

## 5. Final folder structure on GitHub should look like
```
repost-bot/
├── detectors/
│   ├── __init__.py
│   ├── url_detector.py
│   └── image_detector.py
├── bot.py
├── database.py
├── config.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md