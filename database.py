import asyncio

import aiosqlite

from config import DB_PATH

RETENTION_HOURS = 48
SQLITE_BUSY_TIMEOUT_MS = 5000
RETENTION_MODIFIER = f"-{RETENTION_HOURS} hours"

PRAGMA_STATEMENTS = (
    "PRAGMA journal_mode=WAL;",
    "PRAGMA synchronous=NORMAL;",
    "PRAGMA temp_store=MEMORY;",
    f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS};",
)

CREATE_URLS_TABLE = """
CREATE TABLE IF NOT EXISTS posted_urls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    author_name TEXT NOT NULL,
    normalized_url TEXT NOT NULL,
    posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_IMAGES_TABLE = """
CREATE TABLE IF NOT EXISTS posted_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    author_name TEXT NOT NULL,
    image_hash TEXT NOT NULL,
    posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_urls_lookup ON posted_urls(guild_id, normalized_url, posted_at);",
    "CREATE INDEX IF NOT EXISTS idx_urls_cleanup ON posted_urls(posted_at);",
    "CREATE INDEX IF NOT EXISTS idx_images_hash ON posted_images(guild_id, image_hash);",
    "CREATE INDEX IF NOT EXISTS idx_images_lookup ON posted_images(guild_id, posted_at);",
    "CREATE INDEX IF NOT EXISTS idx_images_cleanup ON posted_images(posted_at);",
)

FIND_URL_SQL = """
SELECT channel_id, message_id, author_id, author_name
FROM posted_urls
WHERE guild_id = ? AND normalized_url = ?
  AND posted_at >= datetime('now', ?)
ORDER BY posted_at ASC
LIMIT 1
"""

STORE_URL_SQL = """
INSERT INTO posted_urls(guild_id, channel_id, message_id, author_id, author_name, normalized_url)
VALUES(?,?,?,?,?,?)
"""

FIND_IMAGE_SQL = """
SELECT channel_id, message_id, author_id, author_name, image_hash
FROM posted_images
WHERE guild_id = ?
  AND posted_at >= datetime('now', ?)
ORDER BY posted_at ASC
"""

STORE_IMAGE_SQL = """
INSERT INTO posted_images(guild_id, channel_id, message_id, author_id, author_name, image_hash)
VALUES(?,?,?,?,?,?)
"""

DELETE_OLD_URLS_SQL = "DELETE FROM posted_urls WHERE posted_at < datetime('now', ?)"
DELETE_OLD_IMAGES_SQL = "DELETE FROM posted_images WHERE posted_at < datetime('now', ?)"

_db: aiosqlite.Connection | None = None
_init_lock = asyncio.Lock()
_write_lock = asyncio.Lock()


async def _get_db() -> aiosqlite.Connection:
    if _db is None:
        await init_db()
    if _db is None:
        raise RuntimeError("Database connection is not initialized.")
    return _db


async def init_db():
    global _db

    if _db is not None:
        return

    async with _init_lock:
        if _db is not None:
            return

        db = await aiosqlite.connect(DB_PATH)
        db.row_factory = aiosqlite.Row

        for pragma in PRAGMA_STATEMENTS:
            await db.execute(pragma)

        await db.execute(CREATE_URLS_TABLE)
        await db.execute(CREATE_IMAGES_TABLE)
        for idx in CREATE_INDEXES:
            await db.execute(idx)
        await db.commit()

        _db = db


async def close_db():
    global _db

    async with _init_lock:
        if _db is None:
            return
        await _db.close()
        _db = None


async def find_url(guild_id: str, normalized_url: str):
    db = await _get_db()
    async with db.execute(FIND_URL_SQL, (guild_id, normalized_url, RETENTION_MODIFIER)) as cursor:
        return await cursor.fetchone()


async def store_url(guild_id, channel_id, message_id, author_id, author_name, normalized_url):
    db = await _get_db()
    async with _write_lock:
        await db.execute(
            STORE_URL_SQL,
            (guild_id, channel_id, message_id, author_id, author_name, normalized_url),
        )
        await db.commit()


async def find_image(guild_id: str, image_hash: str, threshold: int):
    try:
        target = int(image_hash, 16)
    except (TypeError, ValueError):
        return None

    db = await _get_db()
    async with db.execute(FIND_IMAGE_SQL, (guild_id, RETENTION_MODIFIER)) as cursor:
        async for row in cursor:
            try:
                stored = int(row["image_hash"], 16)
            except (TypeError, ValueError):
                continue

            if (target ^ stored).bit_count() <= threshold:
                return row
    return None


async def store_image(guild_id, channel_id, message_id, author_id, author_name, image_hash):
    db = await _get_db()
    async with _write_lock:
        await db.execute(
            STORE_IMAGE_SQL,
            (guild_id, channel_id, message_id, author_id, author_name, image_hash),
        )
        await db.commit()


async def cleanup_old_records():
    db = await _get_db()
    async with _write_lock:
        url_result = await db.execute(DELETE_OLD_URLS_SQL, (RETENTION_MODIFIER,))
        image_result = await db.execute(DELETE_OLD_IMAGES_SQL, (RETENTION_MODIFIER,))
        await db.commit()
        await db.execute("PRAGMA optimize;")

    deleted_urls = url_result.rowcount if url_result.rowcount is not None else 0
    deleted_images = image_result.rowcount if image_result.rowcount is not None else 0
    return deleted_urls + deleted_images
