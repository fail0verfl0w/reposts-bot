import aiohttp
import imagehash
from PIL import Image
from io import BytesIO

async def hash_image_url(url: str) -> str | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                content_type = resp.headers.get("Content-Type", "")
                if not content_type.startswith("image/"):
                    return None
                data = await resp.read()
        img = Image.open(BytesIO(data)).convert("RGB")
        phash = imagehash.phash(img)
        return str(phash)
    except Exception:
        return None