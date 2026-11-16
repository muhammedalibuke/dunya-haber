"""Photos: larger versions of feed thumbnails, and cover photos from article pages."""
from __future__ import annotations

import html
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

_BBC = re.compile(r"^(https://ichef\.bbci\.co\.uk/(?:ace/standard|ace/ws|news))/\d{2,4}/")
_WP_SIZE = re.compile(r"-\d{2,4}x\d{2,4}(?=\.(?:jpe?g|png|webp)$)", re.I)
_META = re.compile(r"<meta\b[^>]*>", re.I)
_ATTR = re.compile(r"""([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")
COVER_KEYS = ("og:image:secure_url", "og:image", "og:image:url", "twitter:image", "twitter:image:src")


def upgrade_image_url(url: str) -> str:
    """A larger version of a known-small feed thumbnail; anything else is returned unchanged."""
    m = _BBC.match(url)
    if m:
        return _BBC.sub(m.group(1) + "/976/", url, count=1)
    parts = urlsplit(url)
    if re.fullmatch(r"i\d\.wp\.com", parts.netloc):
        q = [(k, "1200" if k == "w" else v) for k, v in parse_qsl(parts.query, keep_blank_values=True)]
        return urlunsplit(parts._replace(query=urlencode(q)))
    if "/wp-content/uploads/" in parts.path and _WP_SIZE.search(parts.path):
        return urlunsplit(parts._replace(path=_WP_SIZE.sub("", parts.path)))
    return url


def extract_og_image(page: str, base_url: str) -> str | None:
    """The page's own share/cover photo (Open Graph or Twitter card), as an absolute http(s) URL."""
    found: dict[str, str] = {}
    for tag in _META.findall(page):
        attrs = {k.lower(): (a if a else b) for k, a, b in _ATTR.findall(tag)}
        key = (attrs.get("property") or attrs.get("name") or "").lower()
        if key in COVER_KEYS and attrs.get("content") and key not in found:
            found[key] = html.unescape(attrs["content"].strip())
    for key in COVER_KEYS:
        if key in found:
            full = urljoin(base_url, found[key])
            if urlsplit(full).scheme in ("http", "https"):
                return full
    return None
