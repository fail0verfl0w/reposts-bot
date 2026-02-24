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

## Changelog (Unreleased - 2026-02-24)

### Changed
- Refactored [`database.py`](m:/Projects/repost-bot/reposts-bot/database.py) to use a single persistent `aiosqlite` connection instead of opening/closing a connection in every function call.
- Kept existing public API function names/signatures (`init_db`, `find_url`, `store_url`, `find_image`, `store_image`, `cleanup_old_records`) to avoid breaking `bot.py`.
- Switched SQL usage to centralized query constants (`FIND_URL_SQL`, `STORE_URL_SQL`, `FIND_IMAGE_SQL`, etc.) for maintainability and consistent query plans.
- Updated URL lookup query to return only required columns (`channel_id`, `message_id`, `author_id`, `author_name`) instead of `SELECT *`.

### Added
- Connection initialization safeguards with async locks:
  - `_init_lock` for safe one-time init.
  - `_write_lock` to serialize writes/commits.
- SQLite runtime tuning pragmas:
  - `journal_mode=WAL`
  - `synchronous=NORMAL`
  - `temp_store=MEMORY`
  - `busy_timeout=5000`
- New helper functions:
  - `_get_db()` for lazy-safe access to the shared connection.
  - `close_db()` for graceful shutdown support.
- New constants for retention and config centralization:
  - `RETENTION_HOURS`
  - `RETENTION_MODIFIER`
  - `SQLITE_BUSY_TIMEOUT_MS`
- Additional/optimized indexes:
  - `idx_urls_lookup (guild_id, normalized_url, posted_at)`
  - `idx_urls_cleanup (posted_at)`
  - `idx_images_hash (guild_id, image_hash)`
  - `idx_images_lookup (guild_id, posted_at)`
  - `idx_images_cleanup (posted_at)`

### Performance Improvements
- `find_image()` now streams rows via `async for` cursor iteration instead of `fetchall()`, reducing memory pressure for large guild datasets.
- Replaced Hamming distance calculation from `bin(x).count("1")` to `(x).bit_count()` for faster image hash comparison.
- Added fast guard in `find_image()` for invalid hash input (`TypeError`/`ValueError` handling).

### Maintenance/Cleanup
- `cleanup_old_records()` now:
  - Uses shared connection and write lock.
  - Returns total deleted row count.
  - Runs `PRAGMA optimize;` after cleanup.
- Retention window is now centralized and reused in all relevant queries (`48 hours` by default).

### Validation
- Syntax/import check passed with:
  - `py -3 -m py_compile m:\Projects\repost-bot\reposts-bot\database.py`
  - `py -3 -m py_compile m:\Projects\repost-bot\reposts-bot\bot.py`

### Notes
- Recommended follow-up: call `await database.close_db()` during bot shutdown for clean connection teardown.