import discord
import asyncio
import aiohttp
from discord.ext import commands, tasks

import config
import database
from detectors.url_detector import extract_urls, normalize_url, is_shortener
from detectors.image_detector import hash_image_url

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.db_ready = False


def build_message_link(guild_id: int, channel_id: int, message_id: int) -> str:
    return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"


def build_repost_response(original_author_name: str, message_link: str) -> str:
    return (
        f"RTFC - this has been posted by **{original_author_name}**, dumbass.\n"
        f"Original: {message_link}"
    )


async def resolve_shortlink(url: str) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                return str(resp.url)
    except Exception:
        return url


async def process_urls(message: discord.Message) -> bool:
    urls = extract_urls(message.content)
    if not urls:
        return False

    guild_id = str(message.guild.id)

    for raw_url in urls:
        if is_shortener(raw_url):
            raw_url = await resolve_shortlink(raw_url)

        normalized = normalize_url(raw_url)
        existing = await database.find_url(guild_id, normalized)

        if existing:
            if existing["author_id"] == str(message.author.id):
                continue
            link = build_message_link(message.guild.id, existing["channel_id"], existing["message_id"])
            await message.reply(build_repost_response(existing["author_name"], link))
            return True
        else:
            await database.store_url(
                guild_id,
                str(message.channel.id),
                str(message.id),
                str(message.author.id),
                message.author.display_name,
                normalized
            )
    return False


async def process_images(message: discord.Message):
    guild_id = str(message.guild.id)
    image_urls = []

    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith("image/"):
            image_urls.append(attachment.url)

    for embed in message.embeds:
        if embed.image and embed.image.url:
            image_urls.append(embed.image.url)
        if embed.thumbnail and embed.thumbnail.url:
            image_urls.append(embed.thumbnail.url)

    for img_url in image_urls:
        phash = await hash_image_url(img_url)
        if not phash:
            continue

        existing = await database.find_image(guild_id, phash, config.IMAGE_HASH_THRESHOLD)

        if existing:
            if existing["author_id"] == str(message.author.id):
                continue
            link = build_message_link(message.guild.id, existing["channel_id"], existing["message_id"])
            await message.reply(build_repost_response(existing["author_name"], link))
            return
        else:
            await database.store_image(
                guild_id,
                str(message.channel.id),
                str(message.id),
                str(message.author.id),
                message.author.display_name,
                phash
            )


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

    url_was_repost = await process_urls(message)
    if url_was_repost:
        await bot.process_commands(message)
        return

    await asyncio.sleep(2)
    try:
        message = await message.channel.fetch_message(message.id)
    except discord.NotFound:
        return

    await process_images(message)
    await bot.process_commands(message)


@bot.event
async def on_ready():
    await database.init_db()
    bot.db_ready = True
    cleanup_task.start()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


@tasks.loop(hours=6)
async def cleanup_task():
    await database.cleanup_old_records()


@cleanup_task.before_loop
async def before_cleanup():
    await bot.wait_until_ready()


bot.run(config.TOKEN)