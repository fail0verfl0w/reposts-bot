import re
from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse

STRIP_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "ref_src", "ref_url", "s", "t", "igshid", "fbclid", "gclid",
    "mc_cid", "mc_eid", "si",
}

SHORTENER_DOMAINS = {"t.co", "bit.ly", "tinyurl.com", "ow.ly", "buff.ly", "youtu.be"}

URL_PATTERN = re.compile(
    r"https?://[^\s<>\"')\]]+",
    re.IGNORECASE
)

def extract_urls(content: str) -> list[str]:
    return URL_PATTERN.findall(content)

def normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url.strip().rstrip("/"))
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        if netloc.startswith("www."):
            netloc = netloc[4:]

        filtered_params = sorted(
            (k, v) for k, v in parse_qsl(parsed.query)
            if k.lower() not in STRIP_PARAMS
        )

        normalized = urlunparse((
            scheme,
            netloc,
            parsed.path.rstrip("/"),
            parsed.params,
            urlencode(filtered_params),
            ""
        ))
        return normalized
    except Exception:
        return url

def is_shortener(url: str) -> bool:
    try:
        domain = urlparse(url).netloc.lower().lstrip("www.")
        return domain in SHORTENER_DOMAINS
    except Exception:
        return False