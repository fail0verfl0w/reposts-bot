import asyncio
from io import BytesIO

import aiohttp
import discord
import imagehash
from PIL import Image
from discord.ext import commands, tasks

import config
import database
from detectors.url_detector import extract_urls, normalize_url, is_shortener

HTTP_TIMEOUT_SECONDS = 10
SHORTLINK_TIMEOUT_SECONDS = 8
EMBED_SETTLE_SECONDS = 1.5
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10MB


intents = discord.Intents.default()
intents.message_content = True


class RepostBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_ready = False
        self.http_session: aiohttp.ClientSession | None = None

    async def setup_hook(self) -> None:
        timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT_SECONDS)
        connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
        self.http_session = aiohttp.ClientSession(timeout=timeout, connector=connector)

        await database.init_db()
        self.db_ready = True

        if not cleanup_task.is_running():
            cleanup_task.start()

    async def close(self) -> None:
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
        await super().close()


bot = RepostBot(command_prefix="!", intents=intents)


def build_message_link(guild_id: int, channel_id: int, message_id: int) -> str:
    return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"


def build_repost_response(original_author_name: str, message_link: str) -> str:
    return (
        f"RTFC - this has been posted by **{original_author_name}**, dumbass.\n"
        f"Original: {message_link}"
    )


def dedupe_preserve_order(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def get_http_session() -> aiohttp.ClientSession:
    if bot.http_session is None:
        raise RuntimeError("HTTP session is not initialized.")
    return bot.http_session


async def resolve_shortlink(url: str, session: aiohttp.ClientSession) -> str:
    timeout = aiohttp.ClientTimeout(total=SHORTLINK_TIMEOUT_SECONDS)

    try:
        async with session.head(url, allow_redirects=True, timeout=timeout) as resp:
            if resp.status < 400:
                return str(resp.url)
    except Exception:
        pass

    try:
        async with session.get(url, allow_redirects=True, timeout=timeout) as resp:
            return str(resp.url)
    except Exception:
        return url


async def hash_image_url(url: str, session: aiohttp.ClientSession) -> str | None:
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None

            content_type = resp.headers.get("Content-Type", "")
            if not content_type.startswith("image/"):
                return None

            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_IMAGE_BYTES:
                return None

            data = await resp.read()
            if len(data) > MAX_IMAGE_BYTES:
                return None

        with Image.open(BytesIO(data)) as img:
            return str(imagehash.phash(img.convert("RGB")))
    except Exception:
        return None


async def process_urls(
    message: discord.Message,
    guild_id: str,
    channel_id: str,
    message_id: str,
    author_id: str,
    author_name: str,
    session: aiohttp.ClientSession,
) -> bool:
    raw_urls = dedupe_preserve_order(extract_urls(message.content))
    if not raw_urls:
        return False

    seen_normalized: set[str] = set()

    for raw_url in raw_urls:
        if is_shortener(raw_url):
            raw_url = await resolve_shortlink(raw_url, session)

        normalized = normalize_url(raw_url)
        if not normalized or normalized in seen_normalized:
            continue
        seen_normalized.add(normalized)

        existing = await database.find_url(guild_id, normalized)

        if existing:
            if existing["author_id"] == author_id:
                continue

            link = build_message_link(message.guild.id, existing["channel_id"], existing["message_id"])
            await message.reply(build_repost_response(existing["author_name"], link))
            return True

        await database.store_url(
            guild_id,
            channel_id,
            message_id,
            author_id,
            author_name,
            normalized,
        )

    return False


def extract_image_urls(message: discord.Message) -> list[str]:
    image_urls: list[str] = []

    for attachment in message.attachments:
        content_type = attachment.content_type or ""
        if content_type.startswith("image/"):
            image_urls.append(attachment.url)

    for embed in message.embeds:
        if embed.image and embed.image.url:
            image_urls.append(embed.image.url)
        if embed.thumbnail and embed.thumbnail.url:
            image_urls.append(embed.thumbnail.url)

    return dedupe_preserve_order(image_urls)


def should_refetch_for_embeds(message: discord.Message) -> bool:
    if message.attachments or message.embeds:
        return False
    if not message.content:
        return False
    return bool(extract_urls(message.content))


async def process_images(
    message: discord.Message,
    guild_id: str,
    channel_id: str,
    message_id: str,
    author_id: str,
    author_name: str,
    session: aiohttp.ClientSession,
) -> bool:
    image_urls = extract_image_urls(message)
    if not image_urls:
        return False

    seen_hashes: set[str] = set()

    for img_url in image_urls:
        phash = await hash_image_url(img_url, session)
        if not phash or phash in seen_hashes:
            continue
        seen_hashes.add(phash)

        existing = await database.find_image(guild_id, phash, config.IMAGE_HASH_THRESHOLD)

        if existing:
            if existing["author_id"] == author_id:
                continue

            link = build_message_link(message.guild.id, existing["channel_id"], existing["message_id"])
            await message.reply(build_repost_response(existing["author_name"], link))
            return True

        await database.store_image(
            guild_id,
            channel_id,
            message_id,
            author_id,
            author_name,
            phash,
        )

    return False


@bot.event
async def on_message(message: discord.Message):
    if not bot.db_ready:
        return
    if not message.guild:
        return
    if message.author.bot:
        return
    if message.channel.id in config.IGNORED_CHANNEL_IDS:
        return
    if config.WATCHED_GUILD_IDS and message.guild.id not in config.WATCHED_GUILD_IDS:
        return

    guild_id = str(message.guild.id)
    channel_id = str(message.channel.id)
    message_id = str(message.id)
    author_id = str(message.author.id)
    author_name = message.author.display_name
    session = get_http_session()

    url_was_repost = await process_urls(
        message,
        guild_id,
        channel_id,
        message_id,
        author_id,
        author_name,
        session,
    )
    if url_was_repost:
        await bot.process_commands(message)
        return

    image_source = message
    if should_refetch_for_embeds(message):
        await asyncio.sleep(EMBED_SETTLE_SECONDS)
        try:
            image_source = await message.channel.fetch_message(message.id)
        except discord.NotFound:
            await bot.process_commands(message)
            return

    await process_images(
        image_source,
        guild_id,
        channel_id,
        message_id,
        author_id,
        author_name,
        session,
    )
    await bot.process_commands(message)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


@tasks.loop(hours=6)
async def cleanup_task():
    await database.cleanup_old_records()


@cleanup_task.before_loop
async def before_cleanup():
    await bot.wait_until_ready()


bot.run(config.TOKEN)