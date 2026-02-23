import aiosqlite
from config import DB_PATH

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

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_urls ON posted_urls(guild_id, normalized_url);",
    "CREATE INDEX IF NOT EXISTS idx_images ON posted_images(guild_id, image_hash);",
]

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_URLS_TABLE)
        await db.execute(CREATE_IMAGES_TABLE)
        for idx in CREATE_INDEXES:
            await db.execute(idx)
        await db.commit()

async def find_url(guild_id: str, normalized_url: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM posted_urls 
               WHERE guild_id=? AND normalized_url=?
               AND posted_at >= datetime('now', '-48 hours')
               ORDER BY posted_at ASC LIMIT 1""",
            (guild_id, normalized_url)
        ) as cursor:
            return await cursor.fetchone()

async def store_url(guild_id, channel_id, message_id, author_id, author_name, normalized_url):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO posted_urls(guild_id, channel_id, message_id, author_id, author_name, normalized_url) VALUES(?,?,?,?,?,?)",
            (guild_id, channel_id, message_id, author_id, author_name, normalized_url)
        )
        await db.commit()

async def find_image(guild_id: str, image_hash: str, threshold: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM posted_images 
               WHERE guild_id=?
               AND posted_at >= datetime('now', '-48 hours')
               ORDER BY posted_at ASC""",
            (guild_id,)
        ) as cursor:
            rows = await cursor.fetchall()

    target = int(image_hash, 16)
    for row in rows:
        stored = int(row["image_hash"], 16)
        distance = bin(target ^ stored).count("1")
        if distance <= threshold:
            return row
    return None

async def store_image(guild_id, channel_id, message_id, author_id, author_name, image_hash):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO posted_images(guild_id, channel_id, message_id, author_id, author_name, image_hash) VALUES(?,?,?,?,?,?)",
            (guild_id, channel_id, message_id, author_id, author_name, image_hash)
        )
        await db.commit()

async def cleanup_old_records():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM posted_urls WHERE posted_at < datetime('now', '-48 hours')")
        await db.execute("DELETE FROM posted_images WHERE posted_at < datetime('now', '-48 hours')")
        await db.commit()